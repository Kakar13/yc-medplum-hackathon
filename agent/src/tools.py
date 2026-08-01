"""LangChain tools wired to Moss + Medplum + Stedi + wearables + research + capture.

Every tool runs behind the capability gateway: no tool accepts a patient identifier,
and the subject of care is read from the session capability rather than model output.
"""

from __future__ import annotations

import functools
import logging
import re
import time
from typing import Annotated, Any

from langchain_core.tools import tool

from .capability import CapabilityError, get_gateway
from .capture_links import get_capture_store
from .config import get_settings
from .medplum_client import MedplumService

logger = logging.getLogger(__name__)
from .moss_retriever import MossService
from .open_wearables import OpenWearablesService
from . import perio
from .research import ResearchService
from .stedi_client import StediService

_moss: MossService | None = None
_medplum: MedplumService | None = None
_stedi: StediService | None = None
_wearables: OpenWearablesService | None = None
_research: ResearchService | None = None
_session: dict = {
    "patient_id": None,
    "encounter_id": None,
    "last_capture_url": None,
}


def bind_services(
    moss: MossService,
    medplum: MedplumService,
    stedi: StediService | None = None,
    wearables: OpenWearablesService | None = None,
    research: ResearchService | None = None,
) -> None:
    global _moss, _medplum, _stedi, _wearables, _research
    _moss = moss
    _medplum = medplum
    _stedi = stedi or StediService()
    _wearables = wearables or OpenWearablesService()
    _research = research or ResearchService()
    get_gateway().set_audit_sink(medplum)


def get_session() -> dict:
    return _session


def get_moss() -> MossService | None:
    """The Moss instance the tools actually use — so callers warm the same index, not a new one."""
    return _moss


def guarded(fn):
    """Adjudicate a tool call against the active patient capability before running it."""
    gateway = get_gateway()

    @functools.wraps(fn)
    async def awrapper(*args, **kwargs):
        decision = gateway.adjudicate(fn.__name__, kwargs)
        if not decision.allowed:
            return f"DENIED [{decision.control}] {decision.reason}"
        return await fn(*args, **kwargs)

    @functools.wraps(fn)
    def swrapper(*args, **kwargs):
        decision = gateway.adjudicate(fn.__name__, kwargs)
        if not decision.allowed:
            return f"DENIED [{decision.control}] {decision.reason}"
        return fn(*args, **kwargs)

    import inspect

    return awrapper if inspect.iscoroutinefunction(fn) else swrapper


def _subject() -> str:
    """Patient id from the capability — the only sanctioned source."""
    return get_gateway().subject_of_care()


@tool
@guarded
async def moss_search(
    query: Annotated[
        str, "Clinical question or symptom to ground in patient history / protocols"
    ],
    metadata_type: Annotated[
        str,
        "Optional Moss metadata filter type: Condition, MedicationRequest, Protocol, AllergyIntolerance, Coverage, Observation — empty for all",
    ] = "",
) -> str:
    """Moss hybrid search (long-term index + live encounter session). Sub-10ms when loaded.

    Best practices: https://github.com/usemoss/moss — load_index once, session per encounter.
    """
    assert _moss is not None
    session_id = _session.get("encounter_id")
    return await _moss.search_text(
        query,
        session_id=session_id,
        metadata_type=metadata_type or None,
    )


def bind_session_patient(
    medplum: MedplumService | None = None,
) -> tuple[dict[str, Any], Any]:
    """Bind this agent session to exactly one patient, and return (patient, capability).

    Called by the server when a session opens — deliberately *not* left to the model. If
    issuing the capability depended on the agent choosing to call a tool, the binding would be
    contingent on model behaviour, which is the failure mode this gateway exists to remove.
    Takes the service explicitly so binding works before the agent graph is constructed.
    """
    service = medplum or _medplum
    if service is None:
        raise RuntimeError("bind_session_patient needs a MedplumService")
    gateway = get_gateway()
    patient = service.ensure_demo_patient()
    _session["patient_id"] = patient["id"]
    cap = gateway.issue(
        patient_id=patient["id"],
        encounter_id=_session.get("encounter_id"),
        purpose_of_use="TREAT",
        tools=tuple(t.name for t in TOOLS),
        aliases={service.patient_display(patient)},
    )
    return patient, cap


@tool
@guarded
def verify_identity(
    spoken_name: Annotated[str, "The full name the patient just said, verbatim"],
    spoken_date_of_birth: Annotated[
        str, "The date of birth the patient just said, any format, e.g. 'April 12th 1992'"
    ],
) -> str:
    """Check two identifiers against the bound patient before discussing their record.

    Closes the half of the loop the capability cannot. Binding proves the agent writes to one
    record; it says nothing about whether the person speaking is that patient. Verification is
    recorded, never enforced here: it must never sit between a patient and help.
    """
    assert _medplum is not None
    patient = _medplum.ensure_demo_patient()
    expected_name = _medplum.patient_display(patient)
    expected_dob = patient.get("birthDate") or ""

    name_ok = _name_matches(spoken_name, expected_name)
    dob_ok = _dob_matches(spoken_date_of_birth, expected_dob)
    verified = name_ok and dob_ok

    _session["identity"] = {
        "verified": verified,
        "name_match": name_ok,
        "dob_match": dob_ok,
        "identifiers_checked": 2,
        "at": time.time(),
    }
    _medplum.write_audit_event(
        {
            "action": "verify-identity",
            "outcome": "success" if verified else "minor-failure",
            "patient_id": patient["id"],
            "detail": f"name_match={name_ok} dob_match={dob_ok}",
        }
    )
    if verified:
        return (
            f"IDENTITY_VERIFIED two identifiers matched for {expected_name}. "
            "Thank them briefly and move on to why they are here."
        )
    mismatch = "name" if not name_ok else "date of birth"
    return (
        f"IDENTITY_UNVERIFIED the {mismatch} did not match the record. Ask once more, politely. "
        "If it still does not match, say a staff member will confirm their details, continue "
        "taking their history, and do not read anything back from their record."
    )


def _name_matches(spoken: str, expected: str) -> bool:
    """Forgiving on everything except the parts that identify a person.

    Speech-to-text mangles punctuation and case constantly, and patients say "Jordan" where the
    record says "Jordan Lee". Requiring the record's tokens to be present tolerates that without
    tolerating a different name.
    """
    said = {w for w in re.findall(r"[a-z]+", spoken.lower()) if len(w) > 1}
    want = {w for w in re.findall(r"[a-z]+", expected.lower()) if len(w) > 1}
    return bool(want) and want.issubset(said)


_MONTHS = {
    m: i
    for i, m in enumerate(
        "january february march april may june july august september october november "
        "december".split(),
        start=1,
    )
}


def _dob_matches(spoken: str, expected_iso: str) -> bool:
    """Compare a spoken date to an ISO birthDate.

    A date read aloud arrives as "April twelfth, nineteen ninety two" or "4/12/1992", never as
    1992-04-12, so match on the three components rather than on string equality.
    """
    if not expected_iso or len(expected_iso) < 10:
        return False
    year, month, day = expected_iso[:4], int(expected_iso[5:7]), int(expected_iso[8:10])
    low = spoken.lower()
    if year not in low:
        return False
    numbers = {int(n) for n in re.findall(r"\d{1,2}", low)}
    month_ok = month in numbers or any(
        name.startswith(low_word) or low_word.startswith(name[:3])
        for low_word in re.findall(r"[a-z]+", low)
        for name, num in _MONTHS.items()
        if num == month
    )
    return month_ok and day in numbers


@tool
@guarded
def locate_tooth(
    description: Annotated[
        str, "How the patient described the tooth, verbatim, e.g. 'back one on the bottom right'"
    ],
) -> str:
    """Turn a patient's description of a tooth into a specific tooth number.

    Patients cannot name teeth and should not be asked to. Ask about arch and side, which they
    always know, and let this narrow it down.
    """
    # A patient narrows a tooth down over several turns — "one of my back teeth", then "bottom
    # right", then "the last one but one". Each answer is a fragment, so localize against
    # everything they have said, not just the most recent clause.
    said = _session.setdefault("tooth_words", [])
    said.append(description)
    result = perio.locate_tooth(" ".join(said))
    if result["resolved"]:
        _session["focus_tooth"] = result["tooth"]["number"]
        said.clear()
    else:
        _session["focus_tooth"] = None
    if result["resolved"]:
        return (
            f"TOOTH_RESOLVED {result['label']}. Confirm this back to the patient in plain "
            "language — say the position, never the number — then carry on."
        )
    return (
        f"TOOTH_AMBIGUOUS still {len(result['candidates'])} possibilities. "
        f"Ask exactly this: \"{result['question']}\" Do not guess a tooth."
    )


@tool
@guarded
def get_periochart() -> str:
    """The patient's periodontal chart and this tooth's treatment history.

    Use when a dental complaint is localized. Grounds the conversation in what has already been
    done to that tooth, so the patient is not asked to remember their own dental record.
    """
    focus = _session.get("focus_tooth")
    chart = perio.periochart(focus)
    _session["periochart"] = chart
    spoken = perio.periochart_for_voice(focus)
    history = ""
    if focus:
        tooth = next((t for t in chart["teeth"] if t["number"] == focus), None)
        if tooth and tooth["history"]:
            last = tooth["history"][-1]
            history = (
                f" On record for this tooth: {last['event']} on {last['date']}, "
                f"{last['detail']}, by {last['provider']}."
            )
    return f"PERIOCHART {spoken}{history}"


@tool
def ensure_patient() -> str:
    """Confirm which patient this session is bound to, and the scope of that binding.

    The binding is established by the server when the session opens; calling this is
    idempotent and simply reports the active capability.
    """
    assert _medplum is not None
    gateway = get_gateway()
    if gateway.active is not None:
        patient, cap = _medplum.ensure_demo_patient(), gateway.active
    else:
        patient, cap = bind_session_patient()
    return (
        f"Patient/{patient['id']} ready ({_medplum.patient_display(patient)}). "
        f"Capability issued: scope={cap.public()['smart_scope']} "
        f"purpose={cap.purpose_of_use} expires_in={cap.public()['expires_in_seconds']}s. "
        f"Do not pass patient identifiers to any tool — the subject is bound."
    )


@tool
@guarded
async def deep_research(
    complaint: Annotated[
        str, "The presenting complaint in clinical terms, e.g. 'swollen painful knee after running'"
    ],
) -> str:
    """Retrieve real literature (Europe PMC) for any complaint. Cite ONLY what comes back.

    Returns numbered citations. Never invent a source; if nothing is returned, say so.
    """
    assert _research is not None
    brief = await _research.brief(complaint, limit=5)
    _session["last_research"] = brief
    return brief["text"]


@tool
@guarded
async def propose_care_plan(
    title: Annotated[str, "Short plan title, e.g. 'Suspected patellofemoral overuse — initial plan'"],
    summary: Annotated[str, "Why this plan, tailored to THIS patient's history and findings"],
    activities: Annotated[
        str, "Numbered or newline-separated concrete next steps for the patient"
    ],
) -> str:
    """Propose an n=1 plan as a DRAFT CarePlan plus a peer-review Task for a clinician.

    The agent can never activate care. This writes a proposal with AI authorship recorded
    in Provenance; a human reviewer commits or rejects it.
    """
    assert _medplum is not None
    patient_id = _subject()
    if not _session.get("encounter_id"):
        enc = _medplum.create_encounter(patient_id, "Pre-visit check-in")
        _session["encounter_id"] = enc["id"]
        get_gateway().bind_encounter(enc["id"])

    steps = [
        s.strip(" -•\t")
        for s in (activities or "").replace(";", "\n").splitlines()
        if s.strip(" -•\t")
    ]
    citations = (_session.get("last_research") or {}).get("citations") or []
    result = _medplum.propose_care_plan(
        patient_id,
        _session["encounter_id"],
        title=title,
        summary=summary,
        activities=steps or ["Discuss findings with clinician"],
        citations=citations,
    )
    _session["care_plan_id"] = result["care_plan_id"]
    return (
        f"PLAN_PROPOSED status=draft CarePlan/{result['care_plan_id']} "
        f"Task/{result['task_id']} Provenance/{result['provenance_id']} "
        f"citations={len(citations)}. Awaiting clinician review — tell the patient a "
        f"clinician will review before anything is final."
    )


@tool
@guarded
async def chart_to_medplum(
    user_text: Annotated[str, "What the patient said"],
    agent_summary: Annotated[str, "Short clinical summary of this turn"],
) -> str:
    """Write this voice turn into Medplum as Encounter + Observation + Composition."""
    assert _medplum is not None
    result = _medplum.chart_voice_turn(
        patient_id=_subject(),
        encounter_id=_session.get("encounter_id"),
        user_text=user_text,
        agent_text=agent_summary,
    )
    _session["encounter_id"] = result["encounter_id"]
    # Live-call short-term Moss session (usemoss/moss best practice)
    if _moss is not None:
        from uuid import uuid4

        enc = result["encounter_id"]
        try:
            await _moss.add_turn(
                enc, turn_id=f"user-{uuid4().hex[:8]}", text=user_text, role="patient"
            )
            await _moss.add_turn(
                enc,
                turn_id=f"agent-{uuid4().hex[:8]}",
                text=agent_summary,
                role="agent",
            )
        except Exception:
            pass
    return (
        f"Charted to Medplum ({result['mode']}): "
        f"Encounter/{result['encounter_id']} Composition/{result.get('composition_id')}"
    )


@tool
@guarded
def send_photo_capture_link(
    reason: Annotated[
        str,
        "What the photo should show, e.g. 'rash on inner elbow', 'swollen ankle', "
        "'wound edge', 'eye redness', 'medication bottle label'",
    ] = "Clinical photo for the visit",
) -> str:
    """Issue a short-lived secure phone link for the patient to upload a clinical photo.

    Useful for anything visible: skin, swelling, wounds, eyes, gait video stills, or the
    label on a medication the patient can't name. Uses Medplum Binary + securityContext,
    so the phone never receives API credentials. Expires in 15 minutes, single-use.
    """
    assert _medplum is not None
    store = get_capture_store()
    settings = get_settings()

    patient_id = _subject()
    _session["patient_id"] = patient_id
    patient_display = "Patient"
    try:
        if _medplum._client:
            p = _medplum._client.read_resource("Patient", patient_id)
            patient_display = _medplum.patient_display(p)
    except Exception:
        pass

    if not _session.get("encounter_id"):
        enc = _medplum.create_encounter(patient_id, reason)
        _session["encounter_id"] = enc["id"]
        get_gateway().bind_encounter(enc["id"])

    binary = _medplum.create_upload_binary(patient_id, "image/jpeg")
    upload_url = _medplum.presigned_upload_url(binary["id"])
    link = store.issue(
        patient_id=_session["patient_id"],
        encounter_id=_session["encounter_id"],
        binary_id=binary["id"],
        upload_url=upload_url,
        content_type="image/jpeg",
        patient_display=patient_display,
    )
    public = store.public_url(link.token)
    _session["last_capture_url"] = public
    chart_url = f"{settings.public_app_url.rstrip('/')}/chart/{_session['encounter_id']}"
    return (
        f"SECURE_CAPTURE_LINK\n"
        f"url={public}\n"
        f"expires_minutes=15\n"
        f"single_use=true\n"
        f"encounter_id={_session['encounter_id']}\n"
        f"clinician_chart={chart_url}\n"
        f"Tell the patient to open the link on their phone, take the photo, and submit. "
        f"Not a diagnosis — the photo attaches to their chart for the clinician."
    )


# Call-an-ambulance now. Kept narrow on purpose: telling every escalation to dial 911 trains
# patients to ignore the instruction, and it is wrong for the many complaints that need to be
# seen today rather than resuscitated.
EMERGENCY_HINTS = (
    "chest pain", "heart attack", "cardiac", "stroke", "face droop", "slurred",
    "one-sided weakness", "arm numb", "arm numbness", "trouble breathing",
    "can't breathe", "cant breathe", "struggling to breathe", "gasping",
    "anaphyla", "throat closing", "suicid", "self-harm", "bleeding won't stop",
    "severe bleeding", "unconscious", "passed out", "altered consciousness",
    "stiff neck", "worst headache", "coughing up blood",
    # Odontogenic infection that has left the tooth. A lower molar abscess can track into the
    # submandibular and sublingual spaces (Ludwig's angina) and close the airway within hours,
    # and these patients present describing toothache, so a dental complaint is not automatically
    # a routine one. Signs per StatPearls NBK482354 and NBK542165.
    "floor of my mouth", "can't swallow", "cant swallow", "trouble swallowing",
    "difficulty swallowing", "drooling", "can't open my mouth", "cant open my mouth",
    "jaw won't open", "tongue is pushed up", "swelling under my jaw", "swollen neck",
    "muffled voice", "voice sounds different",
)

# Needs to be seen today, but an ambulance is the wrong answer. Exertional breathlessness over
# days sits here; sudden inability to breathe is in the tier above.
URGENT_HINTS = (
    "short of breath", "shortness of breath", "breathless", "dyspnea",
    "high fever", "persistent fever", "dehydrat", "can't keep fluids",
    "spreading redness", "worsening rapidly", "vision loss", "severe pain",
)


@tool
@guarded
async def request_human_handoff(
    reason: Annotated[str, "Why the patient or agent wants a human"],
) -> str:
    """Escalate to a human clinician for co-regulation / algorithm-aversion handoff."""
    # Persist Moss session so the human can resume short-term context. Best-effort, but a
    # failure has to be visible: the handoff otherwise looks fine while the clinician
    # receives none of the conversation.
    context_warning = ""
    if _moss is not None and _session.get("encounter_id"):
        pushed = await _moss.push_session(_session["encounter_id"])
        if pushed is not None and not pushed.get("ok", True):
            logger.warning("handoff context not persisted: %s", pushed.get("error"))
            context_warning = (
                "NOTE FOR THE CLINICIAN: short-term conversation context could not be "
                f"persisted ({pushed.get('error')}). Re-read the chart before advising.\n"
            )
    lowered = (reason or "").lower()
    if any(h in lowered for h in EMERGENCY_HINTS):
        prefix = (
            "EMERGENCY_ESCALATION\n"
            'SAY THIS TO THE PATIENT FIRST, VERBATIM: "This needs emergency care right now '
            '— call 911 or go to the nearest emergency department. Do not wait for this '
            'check-in."\n'
            "Do not run research, cost, or plan steps for this turn.\n"
        )
    elif any(h in lowered for h in URGENT_HINTS):
        prefix = (
            "URGENT_ESCALATION\n"
            'SAY THIS TO THE PATIENT FIRST, VERBATIM: "This should be looked at today. '
            "Please contact the clinic now, or go to urgent care if you can't reach them. "
            'If it gets suddenly worse, or you get chest pain, call 911."\n'
            "Do not run research, cost, or plan steps for this turn.\n"
        )
    else:
        prefix = ""
    return (
        f"{prefix}"
        f"{context_warning}"
        "HUMAN_HANDOFF_REQUESTED\n"
        f"reason={reason}\n"
        f"patient_id={_session.get('patient_id')}\n"
        f"encounter_id={_session.get('encounter_id')}\n"
        "Prepare warm transfer: chart already written; human should acknowledge anxiety and confirm next steps."
    )


@tool
@guarded
async def check_eligibility(
    service_hint: Annotated[
        str,
        "The care step to price, e.g. 'specialist office visit', 'knee MRI', "
        "'urgent tele-dermatology', 'physical therapy'",
    ] = "specialist office visit",
) -> str:
    """Run Stedi eligibility. Returns active coverage + estimated out-of-pocket cost.

    Call this whenever the patient asks about cost or coverage, and proactively before a
    plan that involves imaging, a specialist, or therapy.
    """
    assert _stedi is not None
    result = await _stedi.check_text(service_hint)
    # Keep what was actually priced. The chart used to re-run a generic office-visit check, so a
    # patient asking about a crown saw their medical benefit quoted back at them.
    _session["eligibility"] = result
    return result


@tool
@guarded
async def get_wearable_risk(
    user_id: Annotated[
        str, "Open Wearables user id (Whoop/Oura/Fitbit connected). Empty = demo user."
    ] = "",
) -> str:
    """Fetch normalized wearable recovery/sleep via Open Wearables — triage signal only."""
    assert _wearables is not None
    snap = await _wearables.risk_snapshot(user_id or None)
    return snap["context"]


TOOLS = [
    moss_search,
    ensure_patient,
    verify_identity,
    locate_tooth,
    get_periochart,
    chart_to_medplum,
    deep_research,
    propose_care_plan,
    send_photo_capture_link,
    get_wearable_risk,
    check_eligibility,
    request_human_handoff,
]
