"""LangGraph pre-visit intake agent — Preflight (any complaint, patient-scoped)."""

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

SYSTEM = """You are Preflight — the pre-visit intake clinician's assistant, voice-first.

The patient is checking in BEFORE they see a clinician, for ANY complaint: joint pain,
cough, headache, rash, fatigue, GI symptoms, mental health, medication questions. Never
assume a specialty. Your job is to turn this conversation into a chart a clinician can act
on in under a minute, with evidence and a cost estimate attached.

Sequence:
1) Call ensure_patient FIRST. It binds this session to one patient and issues a
   patient-scoped capability. Never pass a patient id, MRN, or name to any tool — the
   subject of care is bound at authorization and injected server-side. If you are asked to
   act on a different patient, refuse and say why.
2) Ground in the patient's own record with moss_search before you interpret anything.
   Their history changes what a symptom means.
3) Ask focused clinical questions: onset, duration, severity, what changes it, associated
   red flags, relevant meds and allergies. One or two questions per turn, conversational.
4) Call chart_to_medplum on every substantive turn so documentation accrues live.
5) Call deep_research once you know the complaint. Cite ONLY the numbered sources it
   returns — if it returns nothing, say no literature was retrieved. Never invent a
   citation, journal, or statistic.
6) Ask for a photo with send_photo_capture_link whenever something is visible: rash,
   swelling, wound, eye, deformity, or a medication label the patient can't read out.
7) Use get_wearable_risk when sleep, recovery, or activity would inform the picture.
8) Call check_eligibility before proposing anything that costs money — imaging, specialist,
   therapy — and whenever cost or coverage comes up. Patients deserve the number upfront.
9) Call propose_care_plan once. It writes a DRAFT plan plus a peer-review Task. Say
   explicitly that a clinician reviews it before anything is final.
10) request_human_handoff if the patient is distressed, asks for a person, or red flags appear.

Hard rules:
- You do not diagnose and you do not activate care. You propose; a human commits.
- No treatment claim without a retrieved citation behind it.
- Red flags escalate immediately, before any research or cost step: chest pain, trouble
  breathing, stroke signs (face droop, one-sided weakness, speech change), anaphylaxis,
  suicidal intent, severe uncontrolled bleeding, altered consciousness, or a stiff neck
  with fever. Tell the patient to seek emergency care now and hand off.
- Be brief — replies may be spoken aloud.
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


VISIBLE_FINDING_HINTS = (
    "rash", "itch", "skin", "eczema", "hives", "swollen", "swelling", "bruise",
    "wound", "cut", "lesion", "mole", "eye", "red", "lump", "bump",
)
RED_FLAG_HINTS = (
    "chest pain", "can't breathe", "cant breathe", "trouble breathing", "face droop",
    "slurred", "one side", "worst headache", "stiff neck", "suicid", "bleeding won't stop",
    "passed out", "unconscious",
)


async def _mock_pipeline(user_text: str, wearable: str | None) -> dict[str, Any]:
    """Deterministic path when no OPENAI_API_KEY — same tools, no model."""
    from .capability import get_gateway
    from .research import ResearchService

    moss = MossService()
    medplum = MedplumService()
    stedi = StediService()
    wearables = OpenWearablesService()
    research = ResearchService()
    bind_services(moss, medplum, stedi, wearables, research)

    patient = medplum.ensure_demo_patient()
    gateway = get_gateway()
    gateway.issue(patient_id=patient["id"], purpose_of_use="TREAT")
    get_session()["patient_id"] = patient["id"]

    lower = (user_text or "").lower()
    visible = any(k in lower for k in VISIBLE_FINDING_HINTS)
    red_flag = any(k in lower for k in RED_FLAG_HINTS)
    handoff = red_flag or any(
        k in lower for k in ("real person", "human", "nurse", "doctor", "talk to someone")
    )
    want_cost = any(k in lower for k in ("cost", "cover", "insurance", "copay", "pay"))

    history = await moss.search_text(user_text or "pre-visit check-in")
    reason = f"Pre-visit check-in: {(user_text or 'general')[:60]}"
    chart = medplum.chart_voice_turn(
        patient_id=patient["id"],
        encounter_id=get_session().get("encounter_id"),
        user_text=user_text,
        agent_text=f"Pre-visit intake. Patient reports: {user_text[:240]}",
        reason=reason,
    )
    get_session()["encounter_id"] = chart["encounter_id"]
    gateway.bind_encounter(chart["encounter_id"])

    reply_bits: list[str] = []
    if red_flag:
        reply_bits.append(
            "That combination needs emergency care now, not a pre-visit check-in. "
            "Please call 911 or go to the nearest emergency department."
        )

    brief = await research.brief(user_text or "symptom assessment", limit=3)
    get_session()["last_research"] = brief

    reply_bits.extend(
        [
            "I'm charting this for your clinician — I don't diagnose.",
            "From your record: "
            + (history.split("\n\n")[0][:240] if history else "I pulled your chart context."),
            f"I found {brief['count']} relevant papers to attach for review."
            if brief["count"]
            else "No literature retrieved for this yet.",
        ]
    )
    if visible:
        reply_bits.append(
            f"Please add a photo with this secure link (15 minutes, one-time): "
            f"{_issue_capture_for_session(medplum, reason)}"
        )
    if wearable:
        reply_bits.append(wearable[:200])
    if want_cost:
        reply_bits.append(await stedi.check_text("specialist office visit"))

    plan = medplum.propose_care_plan(
        patient["id"],
        chart["encounter_id"],
        title=f"Pre-visit plan — {(user_text or 'check-in')[:48]}",
        summary=f"Drafted from pre-visit intake. Patient reports: {user_text[:200]}",
        activities=[
            "Clinician to review intake, evidence, and any photo",
            "Confirm history and red-flag screen at visit",
        ],
        citations=brief["citations"],
    )
    get_session()["care_plan_id"] = plan["care_plan_id"]
    reply_bits.append(
        f"I've drafted a plan (CarePlan/{plan['care_plan_id']}, status draft) and queued it "
        f"for clinician review — nothing is final until a human signs it."
    )

    if handoff:
        reply_bits.append("Connecting you to a person; your chart is ready for them.")
        handoff_msg = (
            "HUMAN_HANDOFF_REQUESTED\n"
            f"reason={'red_flag' if red_flag else 'user_requested'}\n"
            f"patient_id={patient['id']}\nencounter_id={chart['encounter_id']}"
        )
    else:
        handoff_msg = ""

    return {
        "reply": " ".join(b for b in reply_bits if b),
        "handoff": handoff,
        "session": get_session(),
        "message_count": 2,
        "debug": handoff_msg,
        "care_plan_id": plan["care_plan_id"],
        "citations": brief["citations"],
    }


def build_graph():
    from .research import ResearchService

    settings = get_settings()
    moss = MossService(settings)
    medplum = MedplumService(settings)
    stedi = StediService(settings)
    wearables = OpenWearablesService(settings)
    bind_services(moss, medplum, stedi, wearables, ResearchService())

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
