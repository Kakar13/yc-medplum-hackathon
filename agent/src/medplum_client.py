"""Medplum FHIR helpers (live via pymedplum, or in-memory mock)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .config import Settings, get_settings


class MedplumService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._mock_store: dict[str, list[dict[str, Any]]] = {
            "Patient": [],
            "Encounter": [],
            "Observation": [],
            "Composition": [],
        }
        self._client = None
        if not self.settings.use_mock:
            from pymedplum import MedplumClient

            self._client = MedplumClient(
                base_url=self.settings.medplum_base_url,
                client_id=self.settings.medplum_client_id,
                client_secret=self.settings.medplum_client_secret,
            )

    def ensure_demo_patient(self) -> dict[str, Any]:
        if self.settings.medplum_demo_patient_id and self._client:
            return self._client.read_resource("Patient", self.settings.medplum_demo_patient_id)

        patient = {
            "resourceType": "Patient",
            "name": [{"use": "official", "family": "Lee", "given": ["Jordan"]}],
            "gender": "unknown",
            "birthDate": "1992-04-12",
            "telecom": [{"system": "phone", "value": "+15555550100"}],
        }
        if self._client:
            return self._client.create_resource(patient)

        patient["id"] = self.settings.medplum_demo_patient_id or f"mock-{uuid4().hex[:8]}"
        self._mock_store["Patient"].append(patient)
        return patient

    def create_encounter(self, patient_id: str, reason: str) -> dict[str, Any]:
        encounter = {
            "resourceType": "Encounter",
            "status": "in-progress",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "VR",
                "display": "virtual",
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "reasonCode": [{"text": reason}],
            "period": {"start": datetime.now(timezone.utc).isoformat()},
        }
        if self._client:
            return self._client.create_resource(encounter)

        encounter["id"] = f"enc-{uuid4().hex[:8]}"
        self._mock_store["Encounter"].append(encounter)
        return encounter

    def add_observation(
        self, patient_id: str, encounter_id: str, text: str, code: str = "asserted"
    ) -> dict[str, Any]:
        obs = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"text": code},
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
            "valueString": text,
        }
        if self._client:
            return self._client.create_resource(obs)

        obs["id"] = f"obs-{uuid4().hex[:8]}"
        self._mock_store["Observation"].append(obs)
        return obs

    def write_composition(
        self, patient_id: str, encounter_id: str, title: str, narrative: str
    ) -> dict[str, Any]:
        composition = {
            "resourceType": "Composition",
            "status": "preliminary",
            "type": {"text": "Voice intake note"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "date": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "author": [{"display": "Hackathon Voice Agent"}],
            "section": [
                {
                    "title": "Subjective / intake",
                    "text": {"status": "generated", "div": f"<div>{narrative}</div>"},
                }
            ],
        }
        if self._client:
            return self._client.create_resource(composition)

        composition["id"] = f"comp-{uuid4().hex[:8]}"
        self._mock_store["Composition"].append(composition)
        return composition

    def chart_voice_turn(
        self,
        patient_id: str,
        encounter_id: str | None,
        user_text: str,
        agent_text: str,
        reason: str = "Wearable-triggered voice check-in",
    ) -> dict[str, Any]:
        """Create/continue encounter and append a composition snapshot."""
        if not encounter_id:
            enc = self.create_encounter(patient_id, reason)
            encounter_id = enc["id"]
        self.add_observation(patient_id, encounter_id, f"Patient: {user_text}", "voice-utterance")
        note = f"Patient: {user_text}\nAgent: {agent_text}"
        comp = self.write_composition(
            patient_id, encounter_id, "Live voice chart", note
        )
        return {
            "encounter_id": encounter_id,
            "composition_id": comp.get("id"),
            "mode": "mock" if self.settings.use_mock else "live",
        }

    def dump_mock(self) -> dict[str, Any]:
        return self._mock_store
