"""Live voice bridge — browser mic ⇄ Deepgram Voice Agent ⇄ our capability-gated tools.

Deepgram's Voice Agent API runs listen → think → speak over one socket, which is what makes
sub-second turns achievable: no round trip to us for STT, no second round trip for TTS.
Protocol: https://developers.deepgram.com/docs/voice-agent-message-flow

We still sit in the middle, for three reasons that matter more than the extra hop:

1. The API key stays server-side. A browser holding a Deepgram key is a key you have published.
2. Every function the model wants to call is adjudicated by the capability gateway before it
   runs. Deepgram decides *what* to call; we decide whether it is allowed to touch this patient.
3. The proxy sees the whole event stream, so the clinician and agent panes can watch the same
   conversation live rather than polling the chart afterwards.

Latency notes (measured, see `metrics` in the Ready event):
- Flux (`flux-general-en`, v2) does turn detection in the STT model. `eager_eot_threshold`
  lets the LLM start before the user has fully stopped, which is the single biggest win.
- Output is raw `linear16` with no container, so the browser can queue PCM straight into
  WebAudio instead of waiting on a decoder.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import websockets

from .config import get_settings
from .tools import TOOLS, get_session

logger = logging.getLogger(__name__)

AGENT_WS_URL = "wss://agent.deepgram.com/v1/agent/converse"

# Browser mic rate. 16 kHz is plenty for speech and a quarter the bytes of 48 kHz.
INPUT_SAMPLE_RATE = 16000
# Aura-2 renders at 24 kHz; asking for anything else just adds a resample step.
OUTPUT_SAMPLE_RATE = 24000

# Consecutive failures of one tool before we tell the model to stop trying it.
MAX_TOOL_FAILURES = 3

# Terms Nova/Flux would otherwise guess at. Clinical vocabulary is exactly where a general STT
# model degrades, and a misheard drug name is a charting error, not a typo.
CLINICAL_KEYTERMS = [
    "eczema",
    "atopic dermatitis",
    "triamcinolone",
    "albuterol",
    "prednisone",
    "ibuprofen",
    "acetaminophen",
    "amoxicillin",
    "lisinopril",
    "metformin",
    "sertraline",
    "omeprazole",
    "dyspnea",
    "shortness of breath",
    "palpitations",
    "syncope",
    "paresthesia",
    "erythema",
    "pruritus",
    "urticaria",
    "cellulitis",
    "effusion",
    "meniscus",
    "patellar",
    "plantar fasciitis",
    "sciatica",
    "migraine",
    "photophobia",
    "anaphylaxis",
    "HRV",
    "SpO2",
]

VOICE_SYSTEM_PROMPT = """You are Preflight, a pre-visit intake assistant talking to a patient by voice before they see a clinician.

You are speaking out loud. Keep every reply to one or two sentences. Ask one question at a time. Never read lists, headings, markdown, URLs, or numbers with decimals aloud. Say "about forty" not "40.3".

The patient may have any complaint. Never assume a specialty.

Behaviour:
- Open by asking what brings them in today.
- Ground in their record with moss_search before interpreting anything.
- Ask focused questions: onset, duration, severity, what changes it, red flags, relevant meds and allergies.
- Call chart_to_medplum as the conversation accrues so documentation is written live.
- Call deep_research once the complaint is clear. Cite only what it returns. If it returns nothing, say no literature was retrieved.
- Call send_photo_capture_link when something is visible: rash, swelling, wound, deformity, or a medication label.
- Call get_wearable_risk when sleep or recovery would inform the picture.
- Call check_eligibility before mentioning anything that costs money, and whenever cost or coverage comes up.
- Call propose_care_plan once, and say plainly that a clinician reviews it before anything is final.
- Call request_human_handoff if the patient is distressed, asks for a person, or a red flag appears.

Hard rules:
- Never pass a patient id, name, or medical record number to a tool. The subject of care is bound at authorization. If asked to act on someone else, refuse and say why.
- You do not diagnose and you do not start treatment. You propose; a human commits.
- No treatment claim without a retrieved citation.
- Red flags escalate before any research or cost step: chest pain, trouble breathing, stroke signs, anaphylaxis, suicidal intent, severe bleeding, altered consciousness, stiff neck with fever. Tell them to seek emergency care now, and hand off.
"""

GREETING = "Hi, I'm Preflight. I'll take a few notes before you see the clinician. What's bringing you in today?"


def _json_schema_for(tool: Any) -> dict[str, Any]:
    """Flatten a LangChain tool's args schema into the plain object schema Deepgram expects."""
    schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        return schema
    raw = (
        args_schema.model_json_schema()
        if hasattr(args_schema, "model_json_schema")
        else dict(args_schema)
    )
    for name, prop in (raw.get("properties") or {}).items():
        entry = {
            "type": prop.get("type", "string"),
            "description": prop.get("description") or prop.get("title") or name,
        }
        schema["properties"][name] = entry
    schema["required"] = list(raw.get("required") or [])
    return schema


def function_definitions() -> list[dict[str, Any]]:
    """Expose our guarded tools to Deepgram as client-side functions.

    Client-side rather than server-side on purpose: Deepgram calling our HTTP endpoint directly
    would bypass this process, and with it the capability gateway and the audit ledger.
    """
    defs: list[dict[str, Any]] = []
    for tool in TOOLS:
        defs.append(
            {
                "name": tool.name,
                "description": (tool.description or "").strip().split("\n")[0][:300],
                "parameters": _json_schema_for(tool),
            }
        )
    return defs


def build_settings(
    *, listen_model: str, greeting: str | None = GREETING, history: str = ""
) -> dict[str, Any]:
    """Settings frame for the Voice Agent socket, tuned for turn latency.

    `history` is the patient's own record, injected into the system prompt rather than left for
    the model to go and fetch. Retrieval the model has to elect to do is retrieval that sometimes
    does not happen, and "tailored with full context of your history" is not a claim that should
    hold only on the runs where it remembered.
    """
    s = get_settings()
    is_flux = listen_model.startswith("flux")
    prompt = VOICE_SYSTEM_PROMPT
    if history:
        prompt = (
            f"{VOICE_SYSTEM_PROMPT}\n\n"
            "PATIENT RECORD — retrieved before this call. Treat it as known context: refer to it "
            "naturally, and do not ask about things it already answers. Do not read it aloud as a "
            "list, and do not infer anything it does not say.\n"
            f"{history}\n"
        )

    listen_provider: dict[str, Any] = {"type": "deepgram", "model": listen_model}
    if is_flux:
        # Flux runs on the v2 listen API and owns end-of-turn detection.
        listen_provider["version"] = "v2"
        # Below the 0.7 default: this is a check-in, not a negotiation, so cutting in slightly
        # early costs less than leaving the patient waiting on a pause.
        listen_provider["eot_threshold"] = 0.6
        # Start thinking before the user has fully finished. Costs extra LLM calls, buys the
        # largest single reduction in perceived latency.
        listen_provider["eager_eot_threshold"] = 0.5
        # 5s default is a long silence when someone is describing a symptom and trails off.
        listen_provider["eot_timeout_ms"] = 3000
    else:
        listen_provider["smart_format"] = True  # Flux rejects this
    listen_provider["keyterms"] = CLINICAL_KEYTERMS

    settings: dict[str, Any] = {
        "type": "Settings",
        "tags": ["preflight", "pre-visit-intake"],
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": INPUT_SAMPLE_RATE},
            # container "none" => raw PCM frames the browser can play without decoding.
            "output": {
                "encoding": "linear16",
                "sample_rate": OUTPUT_SAMPLE_RATE,
                "container": "none",
            },
        },
        "agent": {
            "listen": {"provider": listen_provider},
            "think": {
                "provider": {
                    "type": "open_ai",
                    "model": s.openai_model or "gpt-4o-mini",
                    "temperature": 0.3,
                },
                "prompt": prompt,
                "functions": function_definitions(),
            },
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
        },
    }
    if greeting:
        settings["agent"]["greeting"] = greeting
    return settings


@dataclass
class TurnMetrics:
    """Timings we can defend: measured at the proxy, not estimated."""

    user_done_at: float | None = None
    first_audio_ms: float | None = None
    samples: list[float] = field(default_factory=list)

    def mark_user_done(self) -> None:
        self.user_done_at = time.perf_counter()
        self.first_audio_ms = None

    def mark_first_audio(self) -> float | None:
        if self.user_done_at is None or self.first_audio_ms is not None:
            return None
        self.first_audio_ms = (time.perf_counter() - self.user_done_at) * 1000
        self.samples.append(self.first_audio_ms)
        return self.first_audio_ms

    def summary(self) -> dict[str, Any]:
        if not self.samples:
            return {"turns": 0}
        ordered = sorted(self.samples)
        return {
            "turns": len(ordered),
            "last_ms": round(self.samples[-1]),
            "median_ms": round(ordered[len(ordered) // 2]),
            "best_ms": round(ordered[0]),
        }


class VoiceBridge:
    """One patient conversation: browser socket on one side, Deepgram on the other."""

    def __init__(self, send_json: Callable, send_bytes: Callable) -> None:
        self._send_json = send_json
        self._send_bytes = send_bytes
        self.metrics = TurnMetrics()
        self.listen_model = "flux-general-en"
        self._tools = {t.name: t for t in TOOLS}
        self._dg: Any = None
        self._failures: dict[str, int] = {}
        self._research_task: asyncio.Task | None = None
        self._chart_tasks: set[asyncio.Task] = set()
        self._pending_user = ""

    async def _patient_history(self) -> str:
        """Pull the bound patient's record once, to seed the prompt before the call starts."""
        started = time.perf_counter()
        try:
            text = await self._tools["moss_search"].ainvoke(
                {"query": "active conditions, medications, allergies, recent problems"}
            )
        except Exception as exc:  # noqa: BLE001 - a cold index must not block the call
            logger.warning("history preload failed: %s", exc)
            return ""
        if not isinstance(text, str) or text.startswith("DENIED") or "No relevant history" in text:
            return ""
        await self._emit(
            {
                "type": "ToolCall",
                "name": "moss_search",
                "arguments": {"query": "patient record", "trigger": "preload"},
                "denied": False,
                "ms": round((time.perf_counter() - started) * 1000),
                "preview": text[:400],
            }
        )
        return text[:4000]

    def _maybe_chart(self, agent_text: str) -> None:
        """Write the exchange that just happened into the chart, without being asked.

        The brief's claim is that the conversation is charted *as it happens*. Across rehearsals
        the model charted on some runs and not others, which makes the note a lottery. Pairing
        each patient utterance with the reply it produced and writing it here means the record
        exists whatever the model decides to do.
        """
        user_text, self._pending_user = self._pending_user, ""
        if not user_text or not agent_text:
            return

        async def run() -> None:
            started = time.perf_counter()
            try:
                result = await self._tools["chart_to_medplum"].ainvoke(
                    {"user_text": user_text, "agent_summary": agent_text}
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("background charting failed: %s", exc)
                return
            await self._emit(
                {
                    "type": "ToolCall",
                    "name": "chart_to_medplum",
                    "arguments": {"user_text": user_text[:80], "trigger": "automatic"},
                    "denied": isinstance(result, str) and result.startswith("DENIED"),
                    "ms": round((time.perf_counter() - started) * 1000),
                    "preview": (result or "")[:400],
                }
            )

        self._chart_tasks.add(asyncio.create_task(run()))

    def _maybe_research(self, complaint: str) -> None:
        """Kick off literature retrieval on the first real thing the patient says.

        Left to the model this is unreliable — across rehearsals it charted and priced the visit
        but skipped research entirely, so the evidence pane stayed empty and the proposed plan
        had nothing behind it. Running it here makes it a property of the conversation rather
        than of the model's mood. It is deliberately fire-and-forget: results land in the chart,
        so a two-second literature search never delays a spoken reply.
        """
        if self._research_task is not None or len(complaint.strip()) < 20:
            return

        async def run() -> None:
            started = time.perf_counter()
            try:
                result = await self._tools["deep_research"].ainvoke({"complaint": complaint})
            except Exception as exc:  # noqa: BLE001
                logger.warning("background research failed: %s", exc)
                return
            await self._emit(
                {
                    "type": "ToolCall",
                    "name": "deep_research",
                    "arguments": {"complaint": complaint[:80], "trigger": "automatic"},
                    "denied": False,
                    "ms": round((time.perf_counter() - started) * 1000),
                    "preview": (result or "")[:400],
                }
            )

        self._research_task = asyncio.create_task(run())

    def _note_failure(self, name: str, content: str) -> str:
        """Break retry loops.

        A tool that keeps failing will be called again for as long as the model believes it might
        work. Left alone that is an unbounded spend and a patient sitting in silence, so after a
        few attempts we tell the model plainly to stop and carry on without it.
        """
        count = self._failures.get(name, 0) + 1
        self._failures[name] = count
        if count >= MAX_TOOL_FAILURES:
            return (
                f"{content}\n\nThis tool has failed {count} times and is unavailable. Do not call "
                f"{name} again in this conversation. Continue with the patient without it and do "
                "not mention the malfunction."
            )
        return content

    async def _emit(self, payload: dict[str, Any]) -> None:
        try:
            await self._send_json(payload)
        except Exception:  # browser vanished mid-turn; the read loop will notice
            pass

    async def run(self, client_recv: Callable) -> None:
        s = get_settings()
        if not s.deepgram_api_key:
            await self._emit({"type": "Error", "message": "DEEPGRAM_API_KEY not configured"})
            return

        # Flux is the fast path but is not enabled on every account. Fall back rather than
        # leaving the patient with a dead microphone.
        for attempt, model in enumerate(("flux-general-en", "nova-3")):
            self.listen_model = model
            try:
                await self._session(client_recv, model)
                return
            except _SettingsRejected as exc:
                if attempt == 0:
                    logger.warning("Voice Agent rejected %s (%s) — retrying with nova-3", model, exc)
                    await self._emit(
                        {"type": "Notice", "message": f"{model} unavailable, using nova-3"}
                    )
                    continue
                await self._emit({"type": "Error", "message": str(exc)})
                return

    async def _session(self, client_recv: Callable, model: str) -> None:
        s = get_settings()
        async with websockets.connect(
            AGENT_WS_URL,
            additional_headers={"Authorization": f"Token {s.deepgram_api_key}"},
            max_size=None,
            ping_interval=5,
            ping_timeout=20,
        ) as dg:
            self._dg = dg
            history = await self._patient_history()
            await dg.send(json.dumps(build_settings(listen_model=model, history=history)))

            pump = asyncio.create_task(self._pump_client_audio(client_recv))
            try:
                await self._read_deepgram(dg)
            finally:
                # Give writes already in flight a moment to land. Cancelling here would drop the
                # final exchange of the visit — the one the clinician is most likely to read.
                if self._chart_tasks:
                    await asyncio.wait(self._chart_tasks, timeout=3)
                pump.cancel()
                for task in (pump, self._research_task, *self._chart_tasks):
                    if task is None:
                        continue
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass

    async def _pump_client_audio(self, client_recv: Callable) -> None:
        """Browser → Deepgram. Straight relay: any work here shows up as latency."""
        while True:
            msg = await client_recv()
            if msg is None:
                break
            if isinstance(msg, bytes):
                await self._dg.send(msg)
            elif isinstance(msg, dict):
                kind = msg.get("type")
                if kind == "Stop":
                    break
                # Text injection lets the UI put words in the patient's mouth for demos and
                # accessibility without a microphone.
                if kind == "InjectUserMessage":
                    await self._dg.send(
                        json.dumps(
                            {"type": "InjectUserMessage", "content": msg.get("content", "")}
                        )
                    )
                elif kind == "KeepAlive":
                    await self._dg.send(json.dumps({"type": "KeepAlive"}))

    async def _read_deepgram(self, dg: Any) -> None:
        async for raw in dg:
            if isinstance(raw, bytes):
                ms = self.metrics.mark_first_audio()
                if ms is not None:
                    await self._emit(
                        {
                            "type": "Latency",
                            "first_audio_ms": round(ms),
                            "summary": self.metrics.summary(),
                        }
                    )
                await self._send_bytes(raw)
                continue

            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await self._handle_event(event, dg)

    async def _handle_event(self, event: dict[str, Any], dg: Any) -> None:
        kind = event.get("type")

        if kind == "Error":
            message = event.get("description") or event.get("message") or json.dumps(event)
            if "setting" in message.lower() or event.get("code") in {"INVALID_SETTINGS"}:
                raise _SettingsRejected(message)
            await self._emit({"type": "Error", "message": message})
            return

        if kind == "SettingsApplied":
            session = get_session()
            await self._emit(
                {
                    "type": "Ready",
                    "listen_model": self.listen_model,
                    "speak_model": "aura-2-thalia-en",
                    "input_sample_rate": INPUT_SAMPLE_RATE,
                    "output_sample_rate": OUTPUT_SAMPLE_RATE,
                    "tools": list(self._tools),
                    "session": {
                        "patient_id": session.get("patient_id"),
                        "encounter_id": session.get("encounter_id"),
                    },
                }
            )
            return

        if kind == "UserStartedSpeaking":
            # Barge-in: the browser must drop queued audio the instant this arrives, or the
            # agent keeps talking over the patient.
            await self._emit({"type": "BargeIn"})
            return

        if kind == "ConversationText":
            role = event.get("role")
            text = event.get("content") or ""
            if role == "user":
                self.metrics.mark_user_done()
                self._maybe_research(text)
                if len(text.strip()) >= 12:
                    self._pending_user = text
            elif role == "assistant":
                self._maybe_chart(text)
            await self._emit({"type": "Transcript", "role": role, "text": text})
            return

        if kind == "AgentThinking":
            await self._emit({"type": "State", "value": "thinking"})
            return

        if kind == "AgentStartedSpeaking":
            await self._emit({"type": "State", "value": "speaking"})
            return

        if kind == "AgentAudioDone":
            await self._emit({"type": "State", "value": "listening"})
            return

        if kind == "FunctionCallRequest":
            await self._run_functions(event.get("functions") or [], dg)
            return

        if kind in {"Welcome", "PromptUpdated", "SpeakUpdated"}:
            return

        await self._emit({"type": "Raw", "event": event})

    async def _run_functions(self, functions: list[dict[str, Any]], dg: Any) -> None:
        for call in functions:
            if not call.get("client_side", True):
                continue  # Deepgram handles its own built-ins
            name = call.get("name") or ""
            call_id = call.get("id")
            try:
                args = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}

            started = time.perf_counter()
            tool = self._tools.get(name)
            if tool is None:
                content = f"Unknown tool {name}"
                denied = True
            else:
                try:
                    result = await tool.ainvoke(args)
                    content = result if isinstance(result, str) else json.dumps(result)
                    self._failures.pop(name, None)
                except Exception as exc:  # noqa: BLE001 - a tool fault must not kill the call
                    logger.exception("voice tool %s failed", name)
                    # Always name the exception type: an AssertionError stringifies to "" and a
                    # blank error tells the model nothing, so it retries indefinitely.
                    content = f"Tool error: {type(exc).__name__}: {exc}".rstrip(": ")
                    content = self._note_failure(name, content)
                # The gateway returns a DENIED sentinel rather than raising, so the model can
                # explain the refusal to the patient instead of stalling.
                denied = isinstance(content, str) and content.startswith("DENIED")

            elapsed = round((time.perf_counter() - started) * 1000)
            await self._emit(
                {
                    "type": "ToolCall",
                    "name": name,
                    "arguments": args,
                    "denied": denied,
                    "ms": elapsed,
                    "preview": (content or "")[:400],
                }
            )
            await dg.send(
                json.dumps(
                    {
                        "type": "FunctionCallResponse",
                        "id": call_id,
                        "name": name,
                        "content": content,
                    }
                )
            )


class _SettingsRejected(RuntimeError):
    """Deepgram refused our Settings frame — usually a model the account cannot use."""
