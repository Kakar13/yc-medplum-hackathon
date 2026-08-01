"""FastAPI surface: health + text turn + Deepgram function-call webhook stub."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import get_settings
from .graph import build_graph, run_turn
from .open_wearables import OpenWearablesService

app = FastAPI(title="YC Medplum Hackathon Agent", version="0.1.0")

_agent = None
_thread_default = "api-default"


def _get_agent():
    global _agent
    if _agent is None:
        _agent, _, _ = build_graph()
    return _agent


class TurnRequest(BaseModel):
    message: str
    wearable_context: str | None = None
    thread_id: str | None = None


class TurnResponse(BaseModel):
    reply: str
    handoff: bool = False
    session: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health():
    s = get_settings()
    return {
        "ok": True,
        "agent_mode": s.agent_mode,
        "openai": bool(s.openai_api_key),
        "medplum": bool(s.medplum_client_id),
        "moss": bool(s.moss_project_id),
        "deepgram": bool(s.deepgram_api_key),
        "stedi": bool(s.stedi_api_key),
        "open_wearables": bool(s.open_wearables_api_key),
    }


@app.get("/wearables/risk")
async def wearables_risk(user_id: str | None = None):
    """Open Wearables recovery/sleep → triage risk (Whoop/Oura/Fitbit/… via one API)."""
    return await OpenWearablesService().risk_snapshot(user_id)


@app.get("/wearables/oauth/{provider}/authorize")
async def wearables_authorize(provider: str, user_id: str, redirect_uri: str = "http://localhost:3000/connected"):
    """Proxy to Open Wearables OAuth authorize URL for whoop|oura|fitbit|garmin|…"""
    return await OpenWearablesService().authorize_url(provider, user_id, redirect_uri)


@app.post("/turn", response_model=TurnResponse)
async def turn(body: TurnRequest):
    agent = _get_agent()
    tid = body.thread_id or str(uuid.uuid4())
    out = await run_turn(agent, tid, body.message, wearable_context=body.wearable_context)
    return TurnResponse(
        reply=out.get("reply") or "",
        handoff=bool(out.get("handoff")),
        session=out.get("session") or {},
    )


@app.post("/deepgram/function")
async def deepgram_function(payload: dict[str, Any]):
    """Stub for Deepgram Voice Agent FunctionCallRequest (client-side execution).

    Docs: https://developers.deepgram.com/docs/voice-agents-function-calling
    Expects something like:
      { "function_name": "clinical_turn", "input": { "message": "..." } }
    or raw FunctionCallRequest fields — we normalize loosely.
    """
    name = (
        payload.get("function_name")
        or payload.get("name")
        or (payload.get("functions") or [{}])[0].get("name")
    )
    args = (
        payload.get("input")
        or payload.get("arguments")
        or (payload.get("functions") or [{}])[0].get("arguments")
        or {}
    )
    if isinstance(args, str):
        import json

        try:
            args = json.loads(args)
        except Exception:
            args = {"message": args}

    message = args.get("message") or args.get("query") or args.get("text") or ""
    if name in {None, "clinical_turn", "moss_search", "chart_turn"} and message:
        agent = _get_agent()
        out = await run_turn(
            agent,
            args.get("thread_id") or _thread_default,
            message,
            wearable_context=args.get("wearable_context"),
        )
        # Shape compatible with FunctionCallResponse content
        return {
            "type": "FunctionCallResponse",
            "name": name or "clinical_turn",
            "content": out.get("reply"),
            "handoff": out.get("handoff"),
            "session": out.get("session"),
        }

    return {
        "type": "FunctionCallResponse",
        "name": name or "unknown",
        "content": f"Unhandled function stub: {name}",
    }


def main():
    import uvicorn

    uvicorn.run("src.api:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    main()
