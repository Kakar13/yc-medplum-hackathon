"""LangGraph clinical intake agent with Moss + Medplum tools.

Patterns:
- LangGraph prebuilt ReAct: https://docs.langchain.com/oss/python/langgraph/
- Human handoff via tool (co-regulation / algorithm aversion)
- Moss as retrieval tool: https://docs.moss.dev/docs/integrations/langchain
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from .config import get_settings
from .medplum_client import MedplumService
from .moss_retriever import MossService
from .open_wearables import OpenWearablesService
from .stedi_client import StediService
from .tools import TOOLS, bind_services, get_session

SYSTEM = """You are a clinical pre-visit / wearable-triggered voice intake assistant.

Goals:
1) If wearable context is missing, call get_wearable_risk (Open Wearables: Whoop/Oura/Fitbit/…).
2) Ground every medical question in patient history using moss_search.
3) Chart meaningful turns to Medplum with chart_to_medplum (short, clinician-usable summary).
4) Call ensure_patient once at the start of a new session.
5) When cost/coverage comes up, call check_eligibility (Stedi test/mock).
6) If the user is anxious, asks for a person, or stakes feel high, call request_human_handoff.
7) Never claim a diagnosis. Use triage language: risk, next step, when to seek urgent care.
8) Be concise — this may be spoken aloud via TTS.

Wearable context may be provided in the first user message (e.g. resting HR spike).
Acknowledge the signal, ask 2-3 focused questions, retrieve history, chart, suggest next step.
"""


def _tool_by_name():
    return {t.name: t for t in TOOLS}


async def _mock_pipeline(user_text: str, wearable: str | None) -> dict[str, Any]:
    """Deterministic offline path when OPENAI_API_KEY is missing."""
    moss = MossService()
    medplum = MedplumService()
    stedi = StediService()
    wearables = OpenWearablesService()
    bind_services(moss, medplum, stedi, wearables)

    patient = medplum.ensure_demo_patient()
    get_session()["patient_id"] = patient["id"]

    wearable = wearable or await wearables.risk_context_text()
    history = await moss.search_text(user_text or "asthma")
    lower = user_text.lower()
    handoff = any(
        k in lower for k in ("real person", "human", "nurse", "doctor", "talk to someone")
    )
    want_cost = any(k in lower for k in ("cost", "cover", "insurance", "copay", "pay"))
    summary = f"Wearable-triggered check-in. Patient reports: {user_text[:240]}"
    chart = medplum.chart_voice_turn(
        patient_id=patient["id"],
        encounter_id=get_session().get("encounter_id"),
        user_text=user_text,
        agent_text=summary,
        reason=wearable or "Voice check-in",
    )
    get_session()["encounter_id"] = chart["encounter_id"]

    reply_bits = [
        "I see a wearable alert and I'm not diagnosing — just checking in.",
        wearable[:220],
        "From your history: " + history.split("\n\n")[0][:280]
        if history
        else "I pulled your chart context.",
        "How is your breathing right now, and how many times have you used your rescue inhaler today?",
    ]
    if want_cost:
        reply_bits.append(await stedi.check_text("urgent telehealth"))
    if handoff:
        reply_bits.append(
            "Understood — connecting you to a person. Your chart is already started for them."
        )
        handoff_msg = (
            "HUMAN_HANDOFF_REQUESTED\n"
            f"reason=user_requested\npatient_id={patient['id']}\n"
            f"encounter_id={chart['encounter_id']}"
        )
    else:
        handoff_msg = ""

    return {
        "reply": " ".join(reply_bits),
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
        # Return a sentinel object; run_turn detects missing LLM
        return None, moss, medplum

    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    model = ChatOpenAI(
        model=settings.openai_model, temperature=0.3, api_key=settings.openai_api_key
    )
    checkpointer = MemorySaver()
    agent = create_react_agent(
        model,
        tools=TOOLS,
        prompt=SYSTEM,
        checkpointer=checkpointer,
    )
    return agent, moss, medplum


def build_custom_tool_graph():
    """Explicit StateGraph alternative (for Studio / interrupt experiments)."""
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
        m.content
        for m in messages
        if isinstance(getattr(m, "content", None), str)
    )
    handoff = "HUMAN_HANDOFF_REQUESTED" in blob

    return {
        "reply": text,
        "handoff": handoff,
        "session": get_session(),
        "message_count": len(messages),
    }
