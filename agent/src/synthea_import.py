"""Import Synthea (or Synthea-shaped) FHIR Bundles → Moss docs / Medplum.

Overview: https://mitre.github.io/fhir-for-research/modules/synthea-overview
Pre-generated datasets: https://synthea.mitre.org/downloads
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rich.console import Console

from .config import get_settings
from .medplum_client import MedplumService

console = Console()

DEFAULT_BUNDLE = (
    Path(__file__).resolve().parent.parent / "data" / "synthea" / "sample_asthma_bundle.json"
)
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "sample_history.json"

# Resource types worth indexing for history-aware voice intake
INDEX_TYPES = {
    "Patient",
    "Condition",
    "AllergyIntolerance",
    "MedicationRequest",
    "MedicationStatement",
    "Encounter",
    "Observation",
    "Procedure",
    "Immunization",
    "Coverage",
    "CarePlan",
    "DiagnosticReport",
}


def _coding_text(codeable: dict[str, Any] | None) -> str:
    if not codeable:
        return ""
    if codeable.get("text"):
        return str(codeable["text"])
    coding = codeable.get("coding") or []
    if coding:
        c0 = coding[0]
        return str(c0.get("display") or c0.get("code") or "")
    return ""


def _name(patient: dict[str, Any]) -> str:
    names = patient.get("name") or []
    if not names:
        return "Unknown patient"
    n = names[0]
    given = " ".join(n.get("given") or [])
    family = n.get("family") or ""
    return f"{given} {family}".strip() or "Unknown patient"


def resource_to_doc(resource: dict[str, Any]) -> dict[str, Any] | None:
    rtype = resource.get("resourceType")
    if rtype not in INDEX_TYPES:
        return None
    rid = resource.get("id") or "unknown"
    doc_id = f"synthea-{rtype.lower()}-{rid}"

    if rtype == "Patient":
        text = (
            f"Patient {_name(resource)}, "
            f"gender={resource.get('gender')}, DOB={resource.get('birthDate')}. "
            f"Synthetic FHIR patient (Synthea / Synthea-shaped)."
        )
    elif rtype == "Condition":
        text = (
            f"Condition: {_coding_text(resource.get('code'))}. "
            f"Onset={resource.get('onsetDateTime') or resource.get('onsetPeriod', {}).get('start')}. "
            f"Status={_coding_text(resource.get('clinicalStatus')) or resource.get('clinicalStatus')}."
        )
    elif rtype == "AllergyIntolerance":
        rxn = ""
        reactions = resource.get("reaction") or []
        if reactions:
            m = reactions[0].get("manifestation") or []
            rxn = (m[0].get("text") if m else "") or _coding_text(m[0] if m else None)
        text = f"Allergy: {_coding_text(resource.get('code'))}" + (f" — {rxn}." if rxn else ".")
    elif rtype == "MedicationRequest":
        med = resource.get("medicationCodeableConcept") or {}
        dose = ""
        instr = resource.get("dosageInstruction") or []
        if instr:
            dose = instr[0].get("text") or ""
        text = (
            f"Active medication: {_coding_text(med)}. "
            f"{dose} Status={resource.get('status')}."
        ).strip()
    elif rtype == "Encounter":
        text = (
            f"Encounter ({resource.get('status')}): "
            f"{_coding_text((resource.get('type') or [{}])[0]) or (resource.get('class') or {}).get('display')}. "
            f"Reason: {_coding_text((resource.get('reasonCode') or [{}])[0])}. "
            f"Period: {(resource.get('period') or {}).get('start')} → {(resource.get('period') or {}).get('end')}."
        )
    elif rtype == "Observation":
        val = resource.get("valueQuantity") or {}
        vstr = resource.get("valueString")
        if val:
            value = f"{val.get('value')} {val.get('unit') or val.get('code') or ''}".strip()
        else:
            value = vstr or str(resource.get("valueBoolean", ""))
        text = (
            f"Observation: {_coding_text(resource.get('code'))} = {value} "
            f"at {resource.get('effectiveDateTime')}."
        )
    elif rtype == "Coverage":
        payor = ""
        payors = resource.get("payor") or []
        if payors:
            payor = payors[0].get("display") or payors[0].get("reference") or ""
        text = (
            f"Insurance on file: {payor or 'unknown payor'}. "
            f"Status={resource.get('status')}. Prefer Stedi eligibility before paid telehealth."
        )
    else:
        text = f"{rtype}: {_coding_text(resource.get('code')) or json.dumps(resource)[:240]}"

    return {
        "id": doc_id,
        "text": " ".join(text.split()),
        "metadata": {"type": rtype, "source": "synthea"},
    }


def bundle_to_docs(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") or entry
        if not isinstance(resource, dict) or "resourceType" not in resource:
            continue
        doc = resource_to_doc(resource)
        if doc:
            docs.append(doc)
    # Keep wearable/protocol fixtures that Synthea won't generate
    docs.append(
        {
            "id": "protocol-asthma-flare",
            "text": (
                "Asthma flare triage protocol: ask about wheeze, nighttime symptoms, "
                "inhaler use frequency, SpO2 if available, ability to speak full sentences. "
                "Escalate to urgent care/ED if speaking in words only, lips blue, or no "
                "response to rescue inhaler. Otherwise consider same-day telehealth or clinic follow-up."
            ),
            "metadata": {"type": "Protocol", "source": "local"},
        }
    )
    docs.append(
        {
            "id": "obs-baseline-wearable",
            "text": (
                "Baseline wearable pattern: resting heart rate typically 62-68 bpm overnight, "
                "HRV recovery score usually 55-70, sleep 6.5-7.5 hours. Significant deviation: "
                "resting HR >85 or recovery score <35 for 2+ nights."
            ),
            "metadata": {"type": "Observation", "category": "wearable-baseline", "source": "local"},
        }
    )
    return docs


def load_bundle(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("resourceType") != "Bundle":
        raise ValueError(f"{path} is not a FHIR Bundle")
    return data


def import_patient_to_medplum(bundle: dict[str, Any], medplum: MedplumService) -> str | None:
    """Create Patient from first Patient entry (live or mock)."""
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") or {}
        if resource.get("resourceType") != "Patient":
            continue
        payload = {k: v for k, v in resource.items() if k != "id"}
        payload["resourceType"] = "Patient"
        if medplum._client:
            created = medplum._client.create_resource(payload)
            return created.get("id")
        # mock path
        patient = medplum.ensure_demo_patient()
        return patient.get("id")
    return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import Synthea FHIR Bundle → Moss docs JSON")
    parser.add_argument(
        "--bundle",
        type=Path,
        default=DEFAULT_BUNDLE,
        help="Path to Synthea FHIR Bundle (transaction or collection)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Write Moss-ready docs JSON (default: data/sample_history.json)",
    )
    parser.add_argument(
        "--medplum",
        action="store_true",
        help="Also ensure Patient exists in Medplum (live when AGENT_MODE=live)",
    )
    args = parser.parse_args(argv)

    bundle = load_bundle(args.bundle)
    docs = bundle_to_docs(bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(docs, indent=2) + "\n")
    console.print(f"[green]Wrote {len(docs)} docs → {args.out}[/green]")
    for d in docs:
        console.print(f"  • {d['id']}: {d['text'][:90]}...")

    if args.medplum:
        settings = get_settings()
        medplum = MedplumService(settings)
        pid = import_patient_to_medplum(bundle, medplum)
        console.print(f"Medplum Patient id={pid} mode={'live' if not settings.use_mock else 'mock'}")

    console.print(
        "\n[dim]Tip: drop real Synthea exports into data/synthea/ then re-run.\n"
        "Docs: https://mitre.github.io/fhir-for-research/modules/synthea-overview\n"
        "Downloads: https://synthea.mitre.org/downloads[/dim]"
    )


if __name__ == "__main__":
    main()
