"""Multi-provider LLM abstraction for HAARF evaluation harness.

Supports Anthropic (Claude) and Google (Gemini) providers with a common
interface for the agent tool-use loop.  The agent loop works with
Anthropic-format messages internally; each provider converts as needed.

Usage::

    from harness.providers import create_provider

    provider = create_provider(config)
    response = provider.send(system_prompt, messages, tools, config)
    # response.text_blocks, response.tool_calls, response.stop_reason
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Normalised response objects
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A single tool/function call extracted from the model response."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ProviderResponse:
    """Provider-agnostic model response."""
    text_blocks: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use"


# ---------------------------------------------------------------------------
# Base provider
# ---------------------------------------------------------------------------

class BaseProvider:
    """Abstract base for LLM providers."""

    def send(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        config: dict,
    ) -> ProviderResponse:
        """Send a conversation and return a normalised response.

        Parameters
        ----------
        system : str
            System / instruction prompt.
        messages : list[dict]
            Conversation history in **Anthropic format** (the harness's
            internal representation).
        tools : list[dict]
            Tool definitions in **Anthropic format**.
        config : dict
            Experiment config (model, temperature, max_tokens, ...).
        """
        raise NotImplementedError

    @property
    def model_name(self) -> str:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class AnthropicProvider(BaseProvider):
    """Thin wrapper around ``anthropic.Anthropic().messages.create``."""

    def __init__(self) -> None:
        import anthropic  # noqa: F811
        self._client = anthropic.Anthropic()
        self._model: str = ""

    def send(self, system, messages, tools, config):
        self._model = config["model"]

        api_kwargs: dict[str, Any] = {
            "model": config["model"],
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.0),
            "system": system,
            "messages": messages,
        }
        if tools:
            api_kwargs["tools"] = tools

        response = self._client.messages.create(**api_kwargs)

        result = ProviderResponse()
        for block in response.content:
            if block.type == "text":
                result.text_blocks.append(block.text)
            elif block.type == "tool_use":
                result.tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        if response.stop_reason == "end_turn":
            result.stop_reason = "end_turn"
        elif response.stop_reason == "tool_use" or result.tool_calls:
            result.stop_reason = "tool_use"
        else:
            result.stop_reason = "end_turn"

        return result

    @property
    def model_name(self) -> str:
        return self._model


# ---------------------------------------------------------------------------
# Google Gemini provider
# ---------------------------------------------------------------------------

class GeminiProvider(BaseProvider):
    """Wrapper around ``google.generativeai`` with Anthropic-format I/O.

    Internally converts Anthropic tool schemas and messages to the Gemini
    format, calls ``GenerativeModel.generate_content()``, and normalises
    the response back into :class:`ProviderResponse`.
    """

    def __init__(self) -> None:
        import google.generativeai as genai

        self._genai = genai
        api_key = (
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        if not api_key:
            raise ValueError(
                "Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable"
            )
        genai.configure(api_key=api_key)
        self._model_str: str = ""
        self._call_counter: int = 0

    # -- tool schema conversion ---------------------------------------------

    def _convert_schema(self, schema: dict) -> Any:
        """Recursively convert a JSON Schema dict to a Gemini proto Schema."""
        genai = self._genai
        type_map = {
            "object": genai.protos.Type.OBJECT,
            "string": genai.protos.Type.STRING,
            "number": genai.protos.Type.NUMBER,
            "integer": genai.protos.Type.INTEGER,
            "boolean": genai.protos.Type.BOOLEAN,
            "array": genai.protos.Type.ARRAY,
        }
        schema_type = type_map.get(
            schema.get("type", "object"), genai.protos.Type.OBJECT
        )

        kwargs: dict[str, Any] = {"type_": schema_type}

        if "description" in schema:
            kwargs["description"] = schema["description"]
        if "properties" in schema:
            kwargs["properties"] = {
                k: self._convert_schema(v)
                for k, v in schema["properties"].items()
            }
        if "required" in schema:
            kwargs["required"] = schema["required"]
        if "enum" in schema:
            kwargs["enum"] = schema["enum"]
        if "items" in schema:
            kwargs["items"] = self._convert_schema(schema["items"])

        return genai.protos.Schema(**kwargs)

    def _convert_tools(self, anthropic_tools: list[dict]) -> list:
        """Convert Anthropic tool schemas to Gemini function declarations."""
        genai = self._genai
        declarations = []
        for tool in anthropic_tools:
            input_schema = tool.get("input_schema", {})
            decl = genai.protos.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=self._convert_schema(input_schema),
            )
            declarations.append(decl)
        return [genai.protos.Tool(function_declarations=declarations)]

    # -- message conversion --------------------------------------------------

    def _convert_messages(self, messages: list[dict]) -> list:
        """Convert Anthropic-format messages to Gemini Content protos."""
        genai = self._genai
        contents: list = []

        # Build a lookup: tool_use_id -> tool_name (for tool_result conversion)
        id_to_name: dict[str, str] = {}
        for msg in messages:
            if msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        id_to_name[block["id"]] = block["name"]

        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]

            if isinstance(content, str):
                contents.append(
                    genai.protos.Content(
                        role=role,
                        parts=[genai.protos.Part(text=content)],
                    )
                )
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    btype = block.get("type", "")

                    if btype == "text":
                        parts.append(genai.protos.Part(text=block["text"]))

                    elif btype == "tool_use":
                        parts.append(
                            genai.protos.Part(
                                function_call=genai.protos.FunctionCall(
                                    name=block["name"],
                                    args=block.get("input", {}),
                                )
                            )
                        )

                    elif btype == "tool_result":
                        tool_name = id_to_name.get(
                            block.get("tool_use_id", ""), "unknown"
                        )
                        result_content = block.get("content", "")
                        parts.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": result_content},
                                )
                            )
                        )

                if parts:
                    contents.append(
                        genai.protos.Content(role=role, parts=parts)
                    )

        return contents

    # -- send ----------------------------------------------------------------

    def send(self, system, messages, tools, config):
        genai = self._genai
        self._model_str = config["model"]

        model = genai.GenerativeModel(
            self._model_str,
            system_instruction=system,
        )

        gemini_tools = self._convert_tools(tools) if tools else None
        gemini_contents = self._convert_messages(messages)

        gen_config = genai.types.GenerationConfig(
            temperature=config.get("temperature", 0.0),
            max_output_tokens=config.get("max_tokens", 4096),
        )

        response = model.generate_content(
            contents=gemini_contents,
            tools=gemini_tools,
            generation_config=gen_config,
        )

        result = ProviderResponse()

        if not response.candidates:
            return result

        candidate = response.candidates[0]
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call.name:
                self._call_counter += 1
                fc_args = (
                    dict(part.function_call.args)
                    if part.function_call.args
                    else {}
                )
                result.tool_calls.append(
                    ToolCall(
                        id=f"gemini_call_{self._call_counter}",
                        name=part.function_call.name,
                        input=fc_args,
                    )
                )
            elif hasattr(part, "text") and part.text:
                result.text_blocks.append(part.text)

        result.stop_reason = "tool_use" if result.tool_calls else "end_turn"
        return result

    @property
    def model_name(self) -> str:
        return self._model_str


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Model-name prefixes used for auto-detection
_GEMINI_PREFIXES = ("gemini-",)
_ANTHROPIC_PREFIXES = ("claude-",)


def detect_provider(model: str) -> str:
    """Infer the provider from a model name string."""
    lower = model.lower()
    if any(lower.startswith(p) for p in _GEMINI_PREFIXES):
        return "google"
    if any(lower.startswith(p) for p in _ANTHROPIC_PREFIXES):
        return "anthropic"
    raise ValueError(
        f"Cannot auto-detect provider for model '{model}'. "
        f"Set 'provider' explicitly in config.yaml."
    )


def create_provider(config: dict) -> BaseProvider:
    """Create the appropriate provider from experiment config.

    The provider is determined by:
      1. ``config["provider"]`` if set explicitly, else
      2. Auto-detection from ``config["model"]`` prefix.
    """
    provider_name = config.get("provider")
    if not provider_name:
        provider_name = detect_provider(config["model"])

    if provider_name == "anthropic":
        return AnthropicProvider()
    if provider_name == "google":
        return GeminiProvider()

    raise ValueError(f"Unknown provider: {provider_name!r}")
