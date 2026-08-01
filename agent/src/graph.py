"""LangGraph clinical intake agent — FlareCheck (eczema photo + optional wearable)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from .capture_links import get_capture_store
from .config import get_settings
from .medplum_client import MedplumService
from .moss_retriever import MossService
from .open_wearables import OpenWearablesService
from .stedi_client import StediService
from .tools import TOOLS, bind_services, get_session

SYSTEM = """You are FlareCheck — a between-visit flare check-in assistant (voice or text).

Primary demo vertical: eczema / rash flares. Architecture also supports wearable risk.

Goals:
1) Call ensure_patient at the start of a new session.
2) For rash, eczema, itch, skin flare, or "looks worse" — call send_photo_capture_link early and read the URL aloud / in reply (expires 15 minutes, single-use).
3) Ground questions with moss_search (history, meds, allergies, eczema protocol).
4) Chart meaningful turns with chart_to_medplum.
5) Optional: get_wearable_risk if a wearable context may help (sleep/recovery) — never claim diagnosis from wearables.
6) When cost/coverage comes up, call check_eligibility for urgent tele-dermatology.
7) If anxious / asks for a person / high stakes → request_human_handoff.
8) Never diagnose skin disease from a photo. Triage language only: next step, when to seek urgent care.
9) Be concise — may be spoken via TTS.

Escalate urgency (protocol): fever, rapidly spreading, pus/oozing with systemic symptoms, eye/face involvement in infant, or patient can't sleep from pain — suggest urgent care/ED or human handoff.
"""


def _tool_by_name():
    return {t.name: t for t in TOOLS}


def _issue_capture_for_session(medplum: MedplumService, reason: str) -> str:
    store = get_capture_store()
    session = get_session()
    if not session.get("patient_id"):
        patient = medplum.ensure_demo_patient()
        session["patient_id"] = patient["id"]
        display = medplum.patient_display(patient)
    else:
        display = "Patient"
    if not session.get("encounter_id"):
        enc = medplum.create_encounter(session["patient_id"], reason)
        session["encounter_id"] = enc["id"]
    binary = medplum.create_upload_binary(session["patient_id"])
    upload_url = medplum.presigned_upload_url(binary["id"])
    link = store.issue(
        patient_id=session["patient_id"],
        encounter_id=session["encounter_id"],
        binary_id=binary["id"],
        upload_url=upload_url,
        patient_display=display,
    )
    url = store.public_url(link.token)
    session["last_capture_url"] = url
    return url


async def _mock_pipeline(user_text: str, wearable: str | None) -> dict[str, Any]:
    moss = MossService()
    medplum = MedplumService()
    stedi = StediService()
    wearables = OpenWearablesService()
    bind_services(moss, medplum, stedi, wearables)

    patient = medplum.ensure_demo_patient()
    get_session()["patient_id"] = patient["id"]

    lower = user_text.lower()
    skin = any(
        k in lower
        for k in ("eczema", "rash", "itch", "skin", "flare", "dermatitis", "scratch")
    )
    wearable = wearable or (
        None if skin else await wearables.risk_context_text()
    )
    history = await moss.search_text(user_text or ("eczema" if skin else "asthma"))
    handoff = any(
        k in lower for k in ("real person", "human", "nurse", "doctor", "talk to someone")
    )
    want_cost = any(k in lower for k in ("cost", "cover", "insurance", "copay", "pay"))

    reason = "Eczema / rash flare check-in" if skin else (wearable or "Flare check-in")
    summary = f"FlareCheck intake. Patient reports: {user_text[:240]}"
    chart = medplum.chart_voice_turn(
        patient_id=patient["id"],
        encounter_id=get_session().get("encounter_id"),
        user_text=user_text,
        agent_text=summary,
        reason=reason,
    )
    get_session()["encounter_id"] = chart["encounter_id"]

    reply_bits: list[str] = []
    if skin:
        capture_url = _issue_capture_for_session(medplum, reason)
        reply_bits.extend(
            [
                "I'm not diagnosing — just helping get a clear chart for your clinician.",
                "From your history: "
                + (history.split("\n\n")[0][:280] if history else "I pulled your chart context."),
                f"I sent a secure photo link (expires in 15 minutes, one-time use): {capture_url}",
                "Where is the flare, how itchy is it tonight, and any new products or infections around you?",
            ]
        )
    else:
        reply_bits.extend(
            [
                "I see a check-in signal and I'm not diagnosing — just checking in.",
                (wearable or "")[:220],
                "From your history: "
                + (history.split("\n\n")[0][:280] if history else "I pulled your chart context."),
                "How are you feeling right now, and what changed since yesterday?",
            ]
        )
    if want_cost:
        reply_bits.append(await stedi.check_text("urgent tele-dermatology"))
    if handoff:
        reply_bits.append(
            "Understood — connecting you to a person. Your chart (and photo link if issued) is ready for them."
        )
        handoff_msg = (
            "HUMAN_HANDOFF_REQUESTED\n"
            f"reason=user_requested\npatient_id={patient['id']}\n"
            f"encounter_id={chart['encounter_id']}"
        )
    else:
        handoff_msg = ""

    return {
        "reply": " ".join(b for b in reply_bits if b),
        "handoff": handoff,
        "session": get_session(),
        "message_count": 2,
        "debug": handoff_msg,
    }


def build_graph():
    settings = get_settings()
    moss = MossService(settings)
    medplum = MedplumService(settings)
    stedi = StediService(settings)
    wearables = OpenWearablesService(settings)
    bind_services(moss, medplum, stedi, wearables)

    if not settings.openai_api_key:
        return None, moss, medplum

    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    model = ChatOpenAI(
        model=settings.openai_model, temperature=0.3, api_key=settings.openai_api_key
    )
    agent = create_react_agent(
        model,
        tools=TOOLS,
        prompt=SYSTEM,
        checkpointer=MemorySaver(),
    )
    return agent, moss, medplum


def build_custom_tool_graph():
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.openai_model, temperature=0.3, api_key=settings.openai_api_key
    ).bind_tools(TOOLS)
    tools_map = _tool_by_name()

    async def agent_node(state: MessagesState):
        msgs = [SystemMessage(content=SYSTEM)] + state["messages"]
        response = await llm.ainvoke(msgs)
        return {"messages": [response]}

    async def tool_node(state: MessagesState):
        last = state["messages"][-1]
        outputs = []
        for call in getattr(last, "tool_calls", []) or []:
            tool = tools_map[call["name"]]
            result = await tool.ainvoke(call["args"])
            outputs.append(
                ToolMessage(content=str(result), tool_call_id=call["id"], name=call["name"])
            )
        return {"messages": outputs}

    def should_continue(state: MessagesState):
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    g = StateGraph(MessagesState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=MemorySaver())


async def run_turn(
    agent,
    thread_id: str,
    user_text: str,
    wearable_context: str | None = None,
) -> dict[str, Any]:
    if agent is None:
        return await _mock_pipeline(user_text, wearable_context)

    content = user_text
    if wearable_context:
        content = f"[Wearable alert]\n{wearable_context}\n\n[Patient said]\n{user_text}"

    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=content)]},
        config=config,
    )
    messages = result.get("messages", [])
    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    text = ""
    if last_ai:
        text = last_ai.content if isinstance(last_ai.content, str) else str(last_ai.content)

    blob = "\n".join(
        m.content for m in messages if isinstance(getattr(m, "content", None), str)
    )
    handoff = "HUMAN_HANDOFF_REQUESTED" in blob

    return {
        "reply": text,
        "handoff": handoff,
        "session": get_session(),
        "message_count": len(messages),
    }
