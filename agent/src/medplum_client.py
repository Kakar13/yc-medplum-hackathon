"""Medplum FHIR helpers (live via pymedplum, or in-memory mock).

Photo path: Binary + securityContext + $presigned-url upload → Media + DocumentReference.
Docs: https://www.medplum.com/docs/fhir-datastore/binary-data
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from .config import Settings, get_settings

# Process-wide mock CDR so API requests share Patient/Encounter/photo state
_MOCK_STORE: dict[str, list[dict[str, Any]]] = {
    "Patient": [],
    "Encounter": [],
    "Observation": [],
    "Composition": [],
    "Binary": [],
    "Media": [],
    "DocumentReference": [],
}


def _binary_id_from_url(url: str) -> str | None:
    """`Binary/bin-123` or absolute `.../Binary/bin-123` → `bin-123`."""
    if not url or "Binary/" not in url:
        return None
    tail = url.split("Binary/")[-1]
    return tail.split("?")[0].split("/")[0] or None


def _photo_entry(docref: dict[str, Any]) -> dict[str, Any]:
    attachment = ((docref.get("content") or [{}])[0].get("attachment")) or {}
    url = attachment.get("url") or ""
    binary_id = _binary_id_from_url(url)
    return {
        "document_reference_id": docref.get("id"),
        "title": attachment.get("title") or docref.get("description"),
        "content_type": attachment.get("contentType"),
        "url": url,
        "binary_id": binary_id,
        "preview_url": f"/binary/{binary_id}" if binary_id else None,
    }


class MedplumService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._mock_store = _MOCK_STORE
        self._client = None
        if not self.settings.use_mock and self.settings.medplum_client_id:
            from pymedplum import MedplumClient

            self._client = MedplumClient(
                base_url=self.settings.medplum_base_url,
                client_id=self.settings.medplum_client_id,
                client_secret=self.settings.medplum_client_secret,
            )

    @property
    def mode(self) -> str:
        return "live" if self._client else "mock"

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
            created = self._client.create_resource(patient)
            return created

        patient["id"] = self.settings.medplum_demo_patient_id or f"mock-{uuid4().hex[:8]}"
        self._mock_store["Patient"].append(patient)
        return patient

    def patient_display(self, patient: dict[str, Any] | None = None) -> str:
        p = patient or {}
        names = p.get("name") or []
        if not names:
            return "Patient"
        n = names[0]
        given = " ".join(n.get("given") or [])
        family = n.get("family") or ""
        return f"{given} {family}".strip() or "Patient"

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

    def add_quantity_observation(
        self,
        patient_id: str,
        encounter_id: str,
        *,
        value: float,
        unit: str,
        code: str,
        display: str,
        system: str = "http://loinc.org",
        device_display: str | None = None,
    ) -> dict[str, Any]:
        """Coded vital from a wearable — LOINC where one exists, else local code."""
        obs = {
            "resourceType": "Observation",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs",
                        }
                    ]
                }
            ],
            "code": {"coding": [{"system": system, "code": code, "display": display}], "text": display},
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
            "valueQuantity": {
                "value": value,
                "unit": unit,
                "system": "http://unitsofmeasure.org",
                "code": unit,
            },
        }
        if device_display:
            obs["device"] = {"display": device_display}
        if self._client:
            return self._client.create_resource(obs)

        obs["id"] = f"obs-{uuid4().hex[:8]}"
        self._mock_store["Observation"].append(obs)
        return obs

    WEARABLE_VITALS: tuple[tuple[str, str, str, str, str], ...] = (
        # (summary key, LOINC-or-local code, display, unit, code system)
        ("resting_heart_rate_bpm", "40443-4", "Heart rate resting", "/min", "http://loinc.org"),
        ("avg_hrv_sdnn_ms", "80404-7", "Heart rate variability (RMSSD)", "ms", "http://loinc.org"),
        ("avg_spo2_percent", "59408-5", "Oxygen saturation by pulse oximetry", "%", "http://loinc.org"),
        ("skin_temp_celsius", "8310-5", "Body temperature (skin)", "Cel", "http://loinc.org"),
        (
            "recovery_score",
            "recovery-score",
            "Wearable recovery score",
            "%",
            "https://flarecheck.dev/CodeSystem/wearable",
        ),
        ("duration_minutes", "93832-4", "Sleep duration", "min", "http://loinc.org"),
        (
            "efficiency_percent",
            "sleep-efficiency",
            "Sleep efficiency",
            "%",
            "https://flarecheck.dev/CodeSystem/wearable",
        ),
        (
            "awake_minutes",
            "awake-minutes",
            "Time awake during sleep period",
            "min",
            "https://flarecheck.dev/CodeSystem/wearable",
        ),
    )

    def write_wearable_snapshot(
        self,
        patient_id: str,
        encounter_id: str,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Whoop/Open Wearables risk snapshot → coded Observations + chart note."""
        recovery = snapshot.get("recovery") or {}
        sleep = snapshot.get("sleep") or {}
        merged = {**sleep, **recovery}
        provider = snapshot.get("provider") or "wearable"
        device = f"{provider} (via FlareCheck)"

        written: list[str] = []
        for key, code, display, unit, system in self.WEARABLE_VITALS:
            value = merged.get(key)
            if not isinstance(value, (int, float)):
                continue
            obs = self.add_quantity_observation(
                patient_id,
                encounter_id,
                value=round(float(value), 2),
                unit=unit,
                code=code,
                display=display,
                system=system,
                device_display=device,
            )
            written.append(str(obs.get("id")))

        comp = self.write_composition(
            patient_id,
            encounter_id,
            f"Wearable check-in ({provider})",
            snapshot.get("context") or "Wearable snapshot attached.",
            extra_sections=[
                {
                    "title": "Wearable signals",
                    "text": {
                        "status": "generated",
                        "div": (
                            f"<div>Risk level: {snapshot.get('level')} "
                            f"(score {snapshot.get('score')}). "
                            + "; ".join(snapshot.get("reasons") or ["within baseline"])
                            + " — triage signal only, not a diagnosis.</div>"
                        ),
                    },
                }
            ],
        )
        return {
            "observation_ids": written,
            "composition_id": comp.get("id"),
            "provider": provider,
            "level": snapshot.get("level"),
            "mode": self.mode,
        }

    def write_composition(
        self,
        patient_id: str,
        encounter_id: str,
        title: str,
        narrative: str,
        extra_sections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        sections = [
            {
                "title": "Subjective / intake",
                "text": {"status": "generated", "div": f"<div>{narrative}</div>"},
            }
        ]
        if extra_sections:
            sections.extend(extra_sections)
        composition = {
            "resourceType": "Composition",
            "status": "preliminary",
            "type": {"text": "FlareCheck intake note"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "date": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "author": [{"display": "FlareCheck Voice Agent"}],
            "section": sections,
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
        reason: str = "Flare check-in",
    ) -> dict[str, Any]:
        if not encounter_id:
            enc = self.create_encounter(patient_id, reason)
            encounter_id = enc["id"]
        self.add_observation(patient_id, encounter_id, f"Patient: {user_text}", "voice-utterance")
        note = f"Patient: {user_text}\nAgent: {agent_text}"
        comp = self.write_composition(patient_id, encounter_id, "Live flare chart", note)
        return {
            "encounter_id": encounter_id,
            "composition_id": comp.get("id"),
            "mode": self.mode,
        }

    def create_upload_binary(
        self, patient_id: str, content_type: str = "image/jpeg"
    ) -> dict[str, Any]:
        """Create empty Binary with Patient securityContext for presigned upload."""
        binary = {
            "resourceType": "Binary",
            "contentType": content_type,
            "securityContext": {"reference": f"Patient/{patient_id}"},
        }
        if self._client:
            # Prefer create with security context; empty Binary for $presigned-url upload
            try:
                return self._client.create_resource(binary)
            except Exception:
                # Fallback: some servers want raw upload — create tiny placeholder then re-upload
                return self._client.upload_binary(b"", content_type)

        binary["id"] = f"bin-{uuid4().hex[:8]}"
        self._mock_store["Binary"].append(binary)
        return binary

    def presigned_upload_url(self, binary_id: str) -> str:
        """Medplum Binary/$presigned-url?upload=true."""
        if self._client:
            try:
                result = self._client.execute_operation(
                    "Binary",
                    "presigned-url",
                    resource_id=binary_id,
                    params={"upload": "true"},
                    method="GET",
                )
                # Parameters resource or plain dict
                if isinstance(result, dict):
                    if result.get("url"):
                        return str(result["url"])
                    for p in result.get("parameter") or []:
                        if p.get("name") == "url" and p.get("valueString"):
                            return str(p["valueString"])
                        if p.get("name") == "url" and p.get("valueUri"):
                            return str(p["valueUri"])
                # Fallback GET path
                path = f"fhir/R4/Binary/{binary_id}/$presigned-url"
                alt = self._client.get(path, params={"upload": "true"})
                if isinstance(alt, dict):
                    if alt.get("url"):
                        return str(alt["url"])
                    for p in alt.get("parameter") or []:
                        if p.get("name") == "url":
                            return str(p.get("valueString") or p.get("valueUri") or "")
            except Exception as exc:
                # Live fallback: proxy upload through our API (caller sets upload_url)
                return f"proxy://binary/{binary_id}?err={type(exc).__name__}"

        return f"mock://binary/{binary_id}/upload"

    def upload_bytes_to_binary(
        self, binary_id: str, content: bytes, content_type: str, upload_url: str | None = None
    ) -> dict[str, Any]:
        """PUT bytes to Medplum presigned URL, or pymedplum upload if proxy/mock."""
        if upload_url and upload_url.startswith("http") and self._client:
            r = httpx.put(
                upload_url,
                content=content,
                headers={"Content-Type": content_type},
                timeout=60.0,
            )
            r.raise_for_status()
            return self._client.read_resource("Binary", binary_id)

        if self._client:
            # Re-upload via client (creates new Binary) — update reference by creating fresh
            uploaded = self._client.upload_binary(content, content_type)
            return uploaded

        for b in self._mock_store["Binary"]:
            if b.get("id") == binary_id:
                b["data_len"] = len(content)
                b["contentType"] = content_type
                b["_bytes"] = content
                return {k: v for k, v in b.items() if k != "_bytes"}
        binary = {
            "resourceType": "Binary",
            "id": binary_id,
            "contentType": content_type,
            "data_len": len(content),
            "_bytes": content,
        }
        self._mock_store["Binary"].append(binary)
        return {k: v for k, v in binary.items() if k != "_bytes"}

    def read_binary_bytes(self, binary_id: str) -> tuple[bytes, str]:
        """Fetch photo bytes for clinician preview (server-side credentials only)."""
        if self._client:
            # Prefer short-lived presigned download URL, else raw Binary read
            try:
                result = self._client.execute_operation(
                    "Binary", "presigned-url", resource_id=binary_id, method="GET"
                )
                url = ""
                if isinstance(result, dict):
                    url = str(result.get("url") or "")
                    if not url:
                        for p in result.get("parameter") or []:
                            if p.get("name") == "url":
                                url = str(p.get("valueString") or p.get("valueUri") or "")
                if url.startswith("http"):
                    r = httpx.get(url, timeout=30.0)
                    r.raise_for_status()
                    return r.content, r.headers.get(
                        "content-type", "application/octet-stream"
                    )
            except Exception:
                pass
            try:
                meta = self._client.read_resource("Binary", binary_id)
                content_type = str(meta.get("contentType") or "application/octet-stream")
                raw = self._client.download_binary(binary_id)
                data = raw if isinstance(raw, bytes) else bytes(raw)
                return data, content_type
            except Exception as exc:
                raise LookupError(f"Binary/{binary_id} not readable: {exc}") from exc

        for b in self._mock_store["Binary"]:
            if b.get("id") == binary_id:
                data = b.get("_bytes")
                if not data:
                    raise LookupError(f"Binary/{binary_id} has no bytes yet")
                return bytes(data), str(b.get("contentType") or "image/jpeg")
        raise LookupError(f"Binary/{binary_id} not found")

    def finalize_flare_photo(
        self,
        *,
        patient_id: str,
        encounter_id: str,
        binary_id: str,
        content_type: str = "image/jpeg",
        title: str = "Eczema / rash flare photo",
    ) -> dict[str, Any]:
        """Attach Media + DocumentReference to Encounter; append Composition section."""
        now = datetime.now(timezone.utc).isoformat()
        media = {
            "resourceType": "Media",
            "status": "completed",
            "type": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/media-type",
                        "code": "image",
                        "display": "Image",
                    }
                ]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "createdDateTime": now,
            "content": {
                "contentType": content_type,
                "url": f"Binary/{binary_id}",
                "title": title,
            },
        }
        docref = {
            "resourceType": "DocumentReference",
            "status": "current",
            "type": {"text": "Clinical photo"},
            "category": [{"text": "flare-photo"}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "date": now,
            "description": title,
            "context": {"encounter": [{"reference": f"Encounter/{encounter_id}"}]},
            "content": [
                {
                    "attachment": {
                        "contentType": content_type,
                        "url": f"Binary/{binary_id}",
                        "title": title,
                    }
                }
            ],
        }

        if self._client:
            try:
                created_media = self._client.create_resource(media)
            except Exception:
                created_media = {"id": None}
            try:
                created_doc = self._client.create_document_reference(
                    patient_id=patient_id,
                    binary_id=binary_id,
                    content_type=content_type,
                    title=title,
                    description=f"Flare photo for Encounter/{encounter_id}",
                )
            except Exception:
                created_doc = self._client.create_resource(docref)
            self.write_composition(
                patient_id,
                encounter_id,
                "Flare photo attached",
                f"Secure clinical photo uploaded and attached to Encounter/{encounter_id}.",
                extra_sections=[
                    {
                        "title": "Skin photo",
                        "text": {
                            "status": "generated",
                            "div": (
                                f"<div>DocumentReference/{created_doc.get('id')} "
                                f"Binary/{binary_id} — not a diagnosis; for clinician review.</div>"
                            ),
                        },
                    }
                ],
            )
            return {
                "media_id": created_media.get("id"),
                "document_reference_id": created_doc.get("id"),
                "binary_id": binary_id,
                "mode": "live",
            }

        media["id"] = f"media-{uuid4().hex[:8]}"
        docref["id"] = f"docref-{uuid4().hex[:8]}"
        self._mock_store["Media"].append(media)
        self._mock_store["DocumentReference"].append(docref)
        self.write_composition(
            patient_id,
            encounter_id,
            "Flare photo attached",
            f"Mock photo Binary/{binary_id} attached.",
            extra_sections=[
                {
                    "title": "Skin photo",
                    "text": {
                        "status": "generated",
                        "div": f"<div>DocumentReference/{docref['id']} Binary/{binary_id}</div>",
                    },
                }
            ],
        )
        return {
            "media_id": media["id"],
            "document_reference_id": docref["id"],
            "binary_id": binary_id,
            "mode": "mock",
        }

    def get_encounter_chart(self, encounter_id: str) -> dict[str, Any]:
        """Bundle-ish chart payload for clinician UI (BFF)."""
        if self._client:
            encounter = self._client.read_resource("Encounter", encounter_id)
            patient_ref = (encounter.get("subject") or {}).get("reference") or ""
            patient_id = patient_ref.split("/")[-1] if patient_ref else ""
            patient = (
                self._client.read_resource("Patient", patient_id) if patient_id else {}
            )
            observations = self._client.search_resources(
                "Observation", {"encounter": f"Encounter/{encounter_id}"}
            )
            compositions = self._client.search_resources(
                "Composition", {"encounter": f"Encounter/{encounter_id}"}
            )
            docrefs = self._client.search_resources(
                "DocumentReference", {"encounter": f"Encounter/{encounter_id}"}
            )
            # Media search by encounter may vary
            try:
                media = self._client.search_resources(
                    "Media", {"encounter": f"Encounter/{encounter_id}"}
                )
            except Exception:
                media = []
            photos = []
            for d in docrefs or []:
                for c in d.get("content") or []:
                    att = c.get("attachment") or {}
                    url = att.get("url") or ""
                    binary_id = _binary_id_from_url(url)
                    photos.append(
                        {
                            "document_reference_id": d.get("id"),
                            "title": att.get("title") or d.get("description"),
                            "content_type": att.get("contentType"),
                            "url": url,
                            "binary_id": binary_id,
                            "preview_url": f"/binary/{binary_id}" if binary_id else None,
                        }
                    )
            return {
                "mode": "live",
                "encounter": encounter,
                "patient": patient,
                "observations": observations or [],
                "compositions": compositions or [],
                "document_references": docrefs or [],
                "media": media or [],
                "photos": photos,
            }

        encounter = next(
            (e for e in self._mock_store["Encounter"] if e.get("id") == encounter_id),
            {"id": encounter_id, "resourceType": "Encounter"},
        )
        patient_id = (encounter.get("subject") or {}).get("reference", "").split("/")[-1]
        patient = next(
            (p for p in self._mock_store["Patient"] if p.get("id") == patient_id),
            {},
        )
        return {
            "mode": "mock",
            "encounter": encounter,
            "patient": patient,
            "observations": [
                o
                for o in self._mock_store["Observation"]
                if (o.get("encounter") or {}).get("reference") == f"Encounter/{encounter_id}"
            ],
            "compositions": [
                c
                for c in self._mock_store["Composition"]
                if (c.get("encounter") or {}).get("reference") == f"Encounter/{encounter_id}"
            ],
            "document_references": [
                d
                for d in self._mock_store["DocumentReference"]
                if any(
                    (e.get("reference") == f"Encounter/{encounter_id}")
                    for e in ((d.get("context") or {}).get("encounter") or [])
                )
            ],
            "media": [
                m
                for m in self._mock_store["Media"]
                if (m.get("encounter") or {}).get("reference") == f"Encounter/{encounter_id}"
            ],
            "photos": [
                _photo_entry(d)
                for d in self._mock_store["DocumentReference"]
                if any(
                    (e.get("reference") == f"Encounter/{encounter_id}")
                    for e in ((d.get("context") or {}).get("encounter") or [])
                )
            ],
        }

    def dump_mock(self) -> dict[str, Any]:
        return self._mock_store
