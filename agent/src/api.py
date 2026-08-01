"""FastAPI: health, turns, Deepgram stub, secure capture links, clinician BFF."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import (
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from .capability import get_gateway
from .capture_links import get_capture_store
from .config import get_settings
from .graph import build_graph, run_turn
from .medplum_client import MedplumService
from .open_wearables import OpenWearablesService
from .stedi_client import StediService
from .tools import bind_session_patient, get_moss, get_session
from .voice_live import VoiceBridge
from .whoop_client import WhoopClient, WhoopNotConnected, WhoopStateInvalid

logger = logging.getLogger(__name__)

# Uvicorn configures its own loggers and leaves application loggers at WARNING, which silently
# hid the Moss warm-up result — and an unverifiable warm-up is indistinguishable from none.
logging.getLogger("src").setLevel(logging.INFO)
if not logging.getLogger("src").handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:    %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Pay Moss's index load at boot instead of on the patient's first sentence.

    Loading the long-term index costs ~6s, and lazily it lands inside the first `moss_search` of
    a live call — which measured as 6.4s of an 8.2s first response. Warming here moves that cost
    to a moment when nobody is waiting.
    """
    try:
        _get_agent()  # binds Moss/Medplum/Stedi singletons the tools rely on
        moss = get_moss()
        if moss is not None:
            started = time.perf_counter()
            info = await moss.ensure_index()
            logger.info(
                "Moss warm: index=%s docs=%s in %.0fms",
                info.get("index"),
                info.get("doc_count_before", "?"),
                (time.perf_counter() - started) * 1000,
            )
    except Exception:  # noqa: BLE001 - a cold Moss must not stop the API from serving
        logger.warning("Moss warm-up skipped", exc_info=True)
    yield


app = FastAPI(title="Preflight Agent", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = None
_thread_default = "api-default"


def _get_agent():
    global _agent
    if _agent is None:
        _agent, _, _ = build_graph()
    return _agent


def _medplum() -> MedplumService:
    return MedplumService()


class TurnRequest(BaseModel):
    message: str
    wearable_context: str | None = None
    thread_id: str | None = None


class TurnResponse(BaseModel):
    reply: str
    handoff: bool = False
    session: dict[str, Any] = Field(default_factory=dict)


class CaptureLinkRequest(BaseModel):
    patient_id: str | None = None
    encounter_id: str | None = None
    content_type: str = "image/jpeg"
    reason: str = "Clinical photo for pre-visit check-in"


class StartSessionRequest(BaseModel):
    reason: str = "Flare check-in — eczema / rash"
    message: str | None = None


@app.get("/health")
async def health():
    s = get_settings()
    return {
        "ok": True,
        "product": "Preflight",
        "agent_mode": s.agent_mode,
        "medplum_mode": "live" if not s.use_mock and s.medplum_client_id else "mock",
        "openai": bool(s.openai_api_key),
        "medplum": bool(s.medplum_client_id),
        "moss": bool(s.moss_project_id and s.moss_project_key),
        "deepgram": bool(s.deepgram_api_key),
        "stedi": bool(s.stedi_api_key),
        "open_wearables": bool(s.open_wearables_api_key),
        "whoop_configured": bool(s.whoop_client_id and s.whoop_client_secret),
        "whoop_connected": WhoopClient(s).connected,
        "public_app_url": s.public_app_url,
    }


@app.post("/session/start")
async def start_session(body: StartSessionRequest):
    """Ensure Patient + Encounter; optional first agent turn."""
    medplum = _medplum()
    patient = medplum.ensure_demo_patient()
    enc = medplum.create_encounter(patient["id"], body.reason)
    session = get_session()
    session["patient_id"] = patient["id"]
    session["encounter_id"] = enc["id"]
    # Bind the capability here rather than inside a tool: the subject of care must not depend
    # on the model electing to call something.
    _, cap = bind_session_patient(medplum)
    out: dict[str, Any] = {
        "patient_id": patient["id"],
        "patient_display": medplum.patient_display(patient),
        "encounter_id": enc["id"],
        "mode": medplum.mode,
        "session": session,
        "capability": cap.public(),
    }
    if body.message:
        agent = _get_agent()
        turn = await run_turn(agent, str(uuid.uuid4()), body.message)
        out["turn"] = turn
    return out


@app.get("/wearables/risk")
async def wearables_risk(user_id: str | None = None):
    return await OpenWearablesService().risk_snapshot(user_id)


@app.get("/wearables/oauth/{provider}/authorize")
async def wearables_authorize(
    provider: str, user_id: str, redirect_uri: str = "http://localhost:3000/connected"
):
    return await OpenWearablesService().authorize_url(provider, user_id, redirect_uri)


@app.get("/wearables/whoop/status")
async def whoop_status():
    return WhoopClient().status()


@app.get("/wearables/whoop/authorize")
async def whoop_authorize():
    """Start real Whoop OAuth — returns the URL the patient opens once."""
    try:
        return WhoopClient().authorize_url()
    except WhoopNotConnected as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/wearables/whoop/callback")
async def whoop_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Whoop redirects here with ?code — exchange for tokens, then back to the app."""
    s = get_settings()
    if error:
        return RedirectResponse(f"{s.public_app_url}/?whoop=error&reason={error}")
    if not code:
        raise HTTPException(400, "Missing authorization code")
    client = WhoopClient()
    try:
        client.consume_state(state)
    except WhoopStateInvalid:
        return RedirectResponse(f"{s.public_app_url}/?whoop=error&reason=state_mismatch")
    try:
        await client.exchange_code(code)
    except Exception as exc:  # noqa: BLE001 - show failure in the UI, not a stack trace
        return RedirectResponse(f"{s.public_app_url}/?whoop=error&reason={type(exc).__name__}")
    return RedirectResponse(f"{s.public_app_url}/?whoop=connected")


@app.post("/wearables/whoop/disconnect")
async def whoop_disconnect():
    WhoopClient().disconnect()
    return {"ok": True, "connected": False}


@app.get("/wearables/whoop/summaries")
async def whoop_summaries():
    """Raw + normalized latest recovery / sleep from the connected strap."""
    client = WhoopClient()
    if not client.connected:
        raise HTTPException(409, "Whoop not connected — call /wearables/whoop/authorize first")
    try:
        return await client.summaries()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Whoop API error: {exc}") from exc


@app.post("/wearables/to-chart")
async def wearables_to_chart(body: dict[str, Any] | None = None):
    """Wearable snapshot → coded FHIR Observations on the encounter (closed-loop sensing)."""
    body = body or {}
    medplum = _medplum()
    session = get_session()
    patient_id = body.get("patient_id") or session.get("patient_id")
    encounter_id = body.get("encounter_id") or session.get("encounter_id")
    if not patient_id or not encounter_id:
        patient = medplum.ensure_demo_patient()
        enc = medplum.create_encounter(patient["id"], "Wearable-triggered pre-visit check-in")
        patient_id, encounter_id = patient["id"], enc["id"]
        session["patient_id"], session["encounter_id"] = patient_id, encounter_id

    snapshot = await OpenWearablesService().risk_snapshot(body.get("user_id"))
    written = medplum.write_wearable_snapshot(patient_id, encounter_id, snapshot)
    return {
        "ok": True,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "snapshot": snapshot,
        **written,
    }


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


@app.post("/capture-links")
async def create_capture_link(body: CaptureLinkRequest):
    """Issue short-lived secure capture URL (no Medplum secrets to phone)."""
    medplum = _medplum()
    store = get_capture_store()
    session = get_session()

    patient_id = body.patient_id or session.get("patient_id")
    encounter_id = body.encounter_id or session.get("encounter_id")
    if not patient_id:
        patient = medplum.ensure_demo_patient()
        patient_id = patient["id"]
        session["patient_id"] = patient_id
        patient_display = medplum.patient_display(patient)
    else:
        try:
            patient = (
                medplum._client.read_resource("Patient", patient_id)
                if medplum._client
                else next(
                    (p for p in medplum._mock_store["Patient"] if p["id"] == patient_id),
                    {"name": [{"given": ["Jordan"], "family": "Lee"}]},
                )
            )
            patient_display = medplum.patient_display(patient)
        except Exception:
            patient_display = "Patient"

    if not encounter_id:
        enc = medplum.create_encounter(patient_id, body.reason)
        encounter_id = enc["id"]
        session["encounter_id"] = encounter_id

    binary = medplum.create_upload_binary(patient_id, body.content_type)
    binary_id = binary["id"]
    upload_url = medplum.presigned_upload_url(binary_id)
    # Prefer proxy upload through our API (avoids browser CORS to storage.medplum.com)
    api_base = get_settings().public_api_url.rstrip("/")
    link = store.issue(
        patient_id=patient_id,
        encounter_id=encounter_id,
        binary_id=binary_id,
        upload_url=upload_url,
        content_type=body.content_type,
        patient_display=patient_display,
    )
    public = store.public_url(link.token)
    return {
        "token": link.token,
        "url": public,
        "expires_at": link.expires_at,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "binary_id": binary_id,
        "proxy_upload_url": f"{api_base}/capture/{link.token}/upload",
        "mode": medplum.mode,
    }


@app.get("/capture/{token}")
async def get_capture(token: str, s: str | None = None):
    import hmac
    import time

    store = get_capture_store()
    link = store.peek(token)
    if not link or link.used or time.time() > link.expires_at:
        raise HTTPException(404, "Capture link invalid, expired, or already used")
    if s is not None and not hmac.compare_digest(store._sign(token), s):
        raise HTTPException(403, "Invalid capture signature")
    api_base = get_settings().public_api_url.rstrip("/")
    return {
        "token": link.token,
        "patient_display": link.patient_display,
        "patient_id": link.patient_id,
        "encounter_id": link.encounter_id,
        "content_type": link.content_type,
        "expires_at": link.expires_at,
        "proxy_upload_url": f"{api_base}/capture/{token}/upload",
        "direct_upload_url": link.upload_url
        if link.upload_url.startswith("http")
        else None,
        "instructions": (
            "Take a clear photo of the affected skin. This link expires in 15 minutes "
            "and can be used once. Not a diagnosis — for your clinician's chart."
        ),
    }


@app.post("/capture/{token}/upload")
async def upload_capture(
    token: str,
    file: UploadFile = File(...),
    s: str | None = None,
    x_capture_sig: str | None = Header(default=None, alias="X-Capture-Sig"),
):
    """Proxy photo bytes → Medplum Binary (keeps secrets server-side; avoids CORS)."""
    store = get_capture_store()
    sig = s or x_capture_sig
    link = store.get(token, sig=sig) if sig else store.peek(token)
    if not link or link.used:
        raise HTTPException(404, "Capture link invalid or already used")
    import time

    if time.time() > link.expires_at:
        raise HTTPException(410, "Capture link expired")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 12MB)")

    content_type = file.content_type or link.content_type or "image/jpeg"
    medplum = _medplum()
    uploaded_binary_id = link.binary_id
    if link.upload_url.startswith("http"):
        try:
            medplum.upload_bytes_to_binary(
                link.binary_id, content, content_type, upload_url=link.upload_url
            )
        except Exception:
            # Fallback: create new Binary via client upload
            if medplum._client:
                created = medplum._client.upload_binary(content, content_type)
                uploaded_binary_id = created["id"]
            else:
                medplum.upload_bytes_to_binary(link.binary_id, content, content_type)
    else:
        if medplum._client:
            created = medplum._client.upload_binary(content, content_type)
            uploaded_binary_id = created["id"]
        else:
            medplum.upload_bytes_to_binary(link.binary_id, content, content_type)

    finalized = medplum.finalize_flare_photo(
        patient_id=link.patient_id,
        encounter_id=link.encounter_id,
        binary_id=uploaded_binary_id,
        content_type=content_type,
    )
    store.mark_complete(
        token,
        media_id=finalized.get("media_id"),
        document_reference_id=finalized.get("document_reference_id"),
    )
    return {
        "ok": True,
        "encounter_id": link.encounter_id,
        "patient_id": link.patient_id,
        **finalized,
    }


@app.post("/capture/{token}/complete")
async def complete_capture(token: str, body: dict[str, Any] | None = None):
    """Mark complete when browser uploaded directly to Medplum presigned URL."""
    store = get_capture_store()
    link = store.peek(token)
    if not link or link.used:
        raise HTTPException(404, "Capture link invalid or already used")
    import time

    if time.time() > link.expires_at:
        raise HTTPException(410, "Capture link expired")

    binary_id = (body or {}).get("binary_id") or link.binary_id
    medplum = _medplum()
    finalized = medplum.finalize_flare_photo(
        patient_id=link.patient_id,
        encounter_id=link.encounter_id,
        binary_id=binary_id,
        content_type=link.content_type,
    )
    store.mark_complete(
        token,
        media_id=finalized.get("media_id"),
        document_reference_id=finalized.get("document_reference_id"),
    )
    return {"ok": True, "encounter_id": link.encounter_id, **finalized}


@app.get("/chart/{encounter_id}")
async def chart(encounter_id: str):
    """Clinician BFF — Encounter + notes + photos + proposals (server credentials)."""
    medplum = _medplum()
    data = medplum.get_encounter_chart(encounter_id)
    data["eligibility"] = get_session().get("eligibility") or await StediService().check_text(
        "specialist office visit"
    )
    data["proposals"] = medplum.list_proposals(encounter_id=encounter_id)
    data["research"] = (get_session().get("last_research") or {}).get("citations") or []
    data["periochart"] = get_session().get("periochart")
    data["capability"] = (
        get_gateway().active.public() if get_gateway().active else None
    )
    data["handoff_hint"] = (
        "If patient requested a human, continue from this chart — do not restart intake."
    )
    return data


@app.get("/capability")
async def capability():
    """The patient-scoped capability governing the current agent session."""
    gateway = get_gateway()
    cap = gateway.active
    return {
        "active": cap.public() if cap else None,
        "enforcing": gateway.enforcing,
        "stats": gateway.stats(),
        "identity": get_session().get("identity"),
        "principle": (
            "The subject of care is a property of authorization, never a tool argument."
        ),
    }


@app.get("/audit")
async def audit(limit: int = 100):
    """Gateway decision ledger — every allow and deny, with the patient boundary."""
    gateway = get_gateway()
    return {"entries": list(reversed(gateway.ledger(limit))), "stats": gateway.stats()}


@app.get("/review-queue")
async def review_queue():
    """Draft, AI-authored plans awaiting a human decision."""
    return {"proposals": _medplum().list_proposals()}


class ReviewDecision(BaseModel):
    approve: bool = True
    reviewer: str = "Dr. Reviewer"
    note: str = ""


@app.post("/review/{care_plan_id}")
async def review(care_plan_id: str, body: ReviewDecision):
    """Human commits or rejects an AI proposal — the only path to active care."""
    result = _medplum().commit_care_plan(
        care_plan_id,
        reviewer=body.reviewer,
        approve=body.approve,
        note=body.note,
    )
    return result


class RedTeamAttempt(BaseModel):
    tool: str = "propose_care_plan"
    args: dict[str, Any] = Field(
        default_factory=lambda: {
            "mrn": "SYN-003",
            "medication": "metoprolol",
            "dose": "25mg PO BID",
        }
    )


@app.post("/red-team/attempt")
async def red_team_attempt(body: RedTeamAttempt):
    """Adjudicate an arbitrary tool call — the live wrong-patient demonstration.

    Defaults to HAARF RT-4: an order naming SYN-003 while the session is bound elsewhere.
    """
    gateway = get_gateway()
    cap = gateway.active
    decision = gateway.adjudicate(body.tool, body.args)
    return {
        "bound_patient": cap.patient_id if cap else None,
        "attempt": {"tool": body.tool, "args": body.args},
        **decision.public(),
        "referenced_patients": gateway.referenced_patients(body.args),
        "stats": gateway.stats(),
    }


@app.get("/haarf/scorecard")
async def haarf_scorecard():
    """Red-team our gateway with HAARF RT-1..RT-6 and return the scorecard."""
    import json
    from pathlib import Path

    cached = Path(__file__).resolve().parents[1] / "data" / "haarf_scorecard.json"
    if cached.exists():
        return json.loads(cached.read_text())
    raise HTTPException(
        404,
        "No scorecard yet — run: python scripts/haarf_scorecard.py "
        "--json data/haarf_scorecard.json",
    )


@app.get("/binary/{binary_id}")
async def binary_preview(binary_id: str):
    """Stream clinical photo bytes to the clinician UI — Medplum creds stay server-side."""
    medplum = _medplum()
    try:
        content, content_type = medplum.read_binary_bytes(binary_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface upstream failure as 502
        raise HTTPException(502, f"Binary read failed: {exc}") from exc
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=60"},
    )


@app.get("/session")
async def session():
    return get_session()


@app.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)):
    """Browser mic blob → Deepgram Nova-3 transcript (API key stays server-side)."""
    from .voice_deepgram import transcribe_audio

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty audio")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Audio too large")
    try:
        return await transcribe_audio(content, file.content_type or "audio/webm")
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/voice/turn")
async def voice_turn(
    file: UploadFile = File(...),
    thread_id: str | None = Form(default=None),
    wearable_context: str | None = Form(default=None),
):
    """Mic audio → Deepgram STT → LangGraph /turn in one call."""
    from .voice_deepgram import transcribe_audio

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty audio")
    try:
        stt = await transcribe_audio(content, file.content_type or "audio/webm")
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
    transcript = stt.get("transcript") or ""
    if not transcript:
        return {
            "transcript": "",
            "reply": "I didn't catch that — try again a bit closer to the mic.",
            "handoff": False,
            "session": get_session(),
        }
    agent = _get_agent()
    out = await run_turn(
        agent,
        thread_id or str(uuid.uuid4()),
        transcript,
        wearable_context=wearable_context,
    )
    return {
        "transcript": transcript,
        "confidence": stt.get("confidence"),
        "reply": out.get("reply"),
        "handoff": out.get("handoff"),
        "session": out.get("session") or {},
    }


@app.post("/deepgram/function")
async def deepgram_function(payload: dict[str, Any]):
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


@app.websocket("/voice/live")
async def voice_live(ws: WebSocket):
    """Full-duplex voice: browser PCM in, agent PCM out, tool calls adjudicated in between.

    The browser never sees the Deepgram key, and every function the model invokes goes through
    the same capability gateway as the text path — so the wrong-patient denial holds on the
    voice surface too, not just where it is easy to test.
    """
    await ws.accept()

    # Tools reach Moss/Medplum/Stedi through module-level singletons that only build_graph()
    # populates. The voice path does not otherwise need the graph, but without this every tool
    # raises a bare AssertionError and the model retries it forever.
    _get_agent()

    # Bind the patient before a single sample of audio moves. Binding on first tool call would
    # make the subject of care depend on model behaviour, which is the failure this prevents.
    medplum = _medplum()
    session = get_session()
    if not session.get("patient_id"):
        patient, cap = bind_session_patient(medplum)
        if not session.get("encounter_id"):
            enc = medplum.create_encounter(patient["id"], "Voice pre-visit check-in")
            session["encounter_id"] = enc["id"]
        await ws.send_json(
            {
                "type": "Bound",
                "patient_id": patient["id"],
                "patient_display": medplum.patient_display(patient),
                "encounter_id": session["encounter_id"],
                "capability": cap.public(),
            }
        )
    else:
        cap = get_gateway().active  # property, not a method
        if cap is None:
            # Session survived but the capability lapsed — re-bind rather than run unbound.
            patient, cap = bind_session_patient(medplum)
        await ws.send_json(
            {
                "type": "Bound",
                "patient_id": session.get("patient_id"),
                "patient_display": medplum.patient_display(),
                "encounter_id": session.get("encounter_id"),
                "capability": cap.public() if cap else None,
            }
        )

    inbound: asyncio.Queue = asyncio.Queue()

    async def reader() -> None:
        """Demux the browser socket: binary is mic audio, text is control."""
        try:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if (data := msg.get("bytes")) is not None:
                    await inbound.put(data)
                elif (text := msg.get("text")) is not None:
                    try:
                        await inbound.put(json.loads(text))
                    except json.JSONDecodeError:
                        pass
        except WebSocketDisconnect:
            pass
        finally:
            await inbound.put(None)

    bridge = VoiceBridge(send_json=ws.send_json, send_bytes=ws.send_bytes)
    read_task = asyncio.create_task(reader())
    try:
        await bridge.run(inbound.get)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - surface the reason in the UI, not a stack trace
        logger.exception("voice bridge failed")
        try:
            await ws.send_json({"type": "Error", "message": str(exc)})
        except Exception:
            pass
    finally:
        read_task.cancel()
        try:
            await ws.close()
        except Exception:
            pass


def main():
    import uvicorn

    uvicorn.run("src.api:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    main()
