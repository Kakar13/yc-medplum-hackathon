"""Deepgram Voice Agent bridge — LangGraph as the 'think' layer.

Architecture (LangChain voice pattern: Listen → Think → Speak):
https://docs.langchain.com/oss/python/langchain/voice-agent

Deepgram Voice Agent API can own STT+TTS while our LangGraph handles tools
(Moss / Medplum / handoff). For the hackathon we also support a text CLI
without a mic.

Docs: https://developers.deepgram.com/docs/build-a-voice-agent-python
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from .config import get_settings


async def run_text_session(
    turn_fn: Callable[[str], Awaitable[dict[str, Any]]],
    wearable_context: str | None = None,
) -> None:
    """Simple REPL that feeds transcripts into LangGraph (no mic required)."""
    from rich.console import Console

    console = Console()
    console.print("[bold]Clinical voice agent (text mode)[/bold]")
    console.print("Type as the patient. Commands: /handoff, /quit\n")
    if wearable_context:
        console.print(f"[yellow]Wearable context:[/yellow] {wearable_context}\n")

    first = True
    while True:
        user = console.input("[cyan]You> [/cyan]").strip()
        if not user:
            continue
        if user in {"/quit", "/exit", "quit"}:
            break
        if user == "/handoff":
            user = "I want to talk to a real person please."

        ctx = wearable_context if first else None
        first = False
        result = await turn_fn(user) if ctx is None else await _turn_with_ctx(turn_fn, user, ctx)
        console.print(f"[green]Agent>[/green] {result.get('reply')}")
        if result.get("handoff"):
            console.print("[magenta]→ Human handoff requested (co-regulation path)[/magenta]")
        sess = result.get("session") or {}
        if sess.get("encounter_id"):
            console.print(
                f"[dim]Medplum Encounter/{sess['encounter_id']} Patient/{sess.get('patient_id')}[/dim]"
            )


async def _turn_with_ctx(turn_fn, user, ctx):
    # turn_fn from cli closes over wearable; support both signatures
    try:
        return await turn_fn(user, ctx)  # type: ignore[misc]
    except TypeError:
        return await turn_fn(user)


def deepgram_agent_settings(
    system_prompt: str,
    *,
    function_url: str | None = "http://localhost:8080/deepgram/function",
) -> dict[str, Any]:
    """Settings payload for Deepgram Voice Agent WebSocket (reference).

    Function calling: https://developers.deepgram.com/docs/voice-agents-function-calling
    Client-side: omit endpoint; Server-side: point endpoint at our FastAPI stub.
    """
    settings = get_settings()
    clinical_fn: dict[str, Any] = {
        "name": "clinical_turn",
        "description": (
            "Run clinical intake turn: Moss history, Medplum charting, "
            "optional Stedi eligibility via LangGraph backend."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "What the patient just said",
                },
                "wearable_context": {
                    "type": "string",
                    "description": "Optional wearable alert summary",
                },
            },
            "required": ["message"],
        },
    }
    if function_url:
        clinical_fn["url"] = function_url  # server-side execution if supported

    return {
        "type": "Settings",
        "audio": {
            "input": {"encoding": "linear16", "sample_rate": 24000},
            "output": {"encoding": "linear16", "sample_rate": 16000, "container": "wav"},
        },
        "agent": {
            "language": "en",
            "listen": {"provider": {"type": "deepgram", "model": "nova-3"}},
            "think": {
                "provider": {"type": "open_ai", "model": settings.openai_model or "gpt-4o-mini"},
                "prompt": system_prompt,
                "functions": [clinical_fn],
            },
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
            "greeting": (
                "Hi — I'm checking in because your wearable looked off. "
                "This is not a diagnosis. How are you feeling right now?"
            ),
        },
    }


async def smoke_deepgram_key() -> str:
    """Validate Deepgram API key with a tiny REST listen call if key present."""
    settings = get_settings()
    if not settings.deepgram_api_key:
        return "DEEPGRAM_API_KEY not set — voice WS skipped (text mode OK)"

    import httpx

    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.deepgram.com/v1/projects",
            headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            timeout=20,
        )
        if r.status_code < 300:
            return f"Deepgram OK ({r.status_code})"
        return f"Deepgram key check failed: {r.status_code} {r.text[:200]}"


async def transcribe_audio(content: bytes, content_type: str = "audio/webm") -> dict[str, Any]:
    """Nova-3 pre-recorded listen — browser mic → text for /turn.

    Docs: https://developers.deepgram.com/docs/pre-recorded-audio
    """
    settings = get_settings()
    if not settings.deepgram_api_key:
        raise RuntimeError("DEEPGRAM_API_KEY not set")

    import httpx

    params = {
        "model": "nova-3",
        "smart_format": "true",
        "punctuate": "true",
        "language": "en",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.deepgram.com/v1/listen",
            params=params,
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": content_type or "application/octet-stream",
            },
            content=content,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Deepgram listen failed: {r.status_code} {r.text[:300]}")
        data = r.json()
    alt = (
        (((data.get("results") or {}).get("channels") or [{}])[0].get("alternatives") or [{}])[0]
    )
    transcript = (alt.get("transcript") or "").strip()
    return {
        "transcript": transcript,
        "confidence": alt.get("confidence"),
        "model": "nova-3",
    }
