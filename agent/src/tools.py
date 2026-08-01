"""LangChain tools wired to Moss + Medplum + Stedi + Open Wearables."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

from .medplum_client import MedplumService
from .moss_retriever import MossService
from .open_wearables import OpenWearablesService
from .stedi_client import StediService

_moss: MossService | None = None
_medplum: MedplumService | None = None
_stedi: StediService | None = None
_wearables: OpenWearablesService | None = None
_session: dict = {
    "patient_id": None,
    "encounter_id": None,
}


def bind_services(
    moss: MossService,
    medplum: MedplumService,
    stedi: StediService | None = None,
    wearables: OpenWearablesService | None = None,
) -> None:
    global _moss, _medplum, _stedi, _wearables
    _moss = moss
    _medplum = medplum
    _stedi = stedi or StediService()
    _wearables = wearables or OpenWearablesService()


def get_session() -> dict:
    return _session


@tool
async def moss_search(query: Annotated[str, "Clinical question or symptom to ground in patient history / protocols"]) -> str:
    """Search patient history, meds, allergies, and triage protocols via Moss (sub-10ms when live)."""
    assert _moss is not None
    return await _moss.search_text(query)


@tool
def ensure_patient() -> str:
    """Ensure demo Patient exists in Medplum; returns Patient id."""
    assert _medplum is not None
    patient = _medplum.ensure_demo_patient()
    _session["patient_id"] = patient["id"]
    return f"Patient/{patient['id']} ready ({patient.get('name')})"


@tool
def chart_to_medplum(
    user_text: Annotated[str, "What the patient said"],
    agent_summary: Annotated[str, "Short clinical summary of this turn"],
) -> str:
    """Write this voice turn into Medplum as Encounter + Observation + Composition."""
    assert _medplum is not None
    if not _session.get("patient_id"):
        patient = _medplum.ensure_demo_patient()
        _session["patient_id"] = patient["id"]
    result = _medplum.chart_voice_turn(
        patient_id=_session["patient_id"],
        encounter_id=_session.get("encounter_id"),
        user_text=user_text,
        agent_text=agent_summary,
    )
    _session["encounter_id"] = result["encounter_id"]
    return (
        f"Charted to Medplum ({result['mode']}): "
        f"Encounter/{result['encounter_id']} Composition/{result.get('composition_id')}"
    )


@tool
def request_human_handoff(
    reason: Annotated[str, "Why the patient or agent wants a human"],
) -> str:
    """Escalate to a human clinician for co-regulation / algorithm-aversion handoff.

    Does not replace care — pauses agentic flow and returns a handoff packet.
    """
    return (
        "HUMAN_HANDOFF_REQUESTED\n"
        f"reason={reason}\n"
        f"patient_id={_session.get('patient_id')}\n"
        f"encounter_id={_session.get('encounter_id')}\n"
        "Prepare warm transfer: chart already written; human should acknowledge anxiety and confirm next steps."
    )


@tool
async def check_eligibility(
    service_hint: Annotated[
        str, "What care step to price, e.g. urgent telehealth or specialist visit"
    ] = "urgent telehealth",
) -> str:
    """Run Stedi eligibility (test mode / mock). Returns active coverage + estimated copay."""
    assert _stedi is not None
    return await _stedi.check_text(service_hint)


@tool
async def get_wearable_risk(
    user_id: Annotated[
        str, "Open Wearables user id (Whoop/Oura/Fitbit connected). Empty = demo user."
    ] = "",
) -> str:
    """Fetch normalized wearable recovery/sleep via Open Wearables and return a triage risk signal.

    Covers Whoop, Oura, Fitbit, Garmin, etc. through one API. Not a diagnosis.
    """
    assert _wearables is not None
    snap = await _wearables.risk_snapshot(user_id or None)
    return snap["context"]


TOOLS = [
    moss_search,
    ensure_patient,
    chart_to_medplum,
    get_wearable_risk,
    check_eligibility,
    request_human_handoff,
]
