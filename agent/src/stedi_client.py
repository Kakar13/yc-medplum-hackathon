"""Stedi eligibility — mock fixtures or live test-mode API.

API: POST https://healthcare.us.stedi.com/2024-04-01/change/medicalnetwork/eligibility/v3
Auth: Authorization: <api_key>
Docs: https://www.stedi.com/docs/healthcare/test-mode
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings, get_settings

STEDI_ELIGIBILITY_URL = (
    "https://healthcare.us.stedi.com/2024-04-01/change/medicalnetwork/eligibility/v3"
)

# Fixture shaped like a simplified benefits summary (not full 271)
MOCK_BENEFITS = {
    "payer": "UnitedHealthcare (mock)",
    "tradingPartnerServiceId": "87726",
    "active": True,
    "planStatus": "Active Coverage",
    "copay_urgent_care_usd": 40,
    "copay_specialist_usd": 50,
    "deductible_remaining_usd": 250,
    "notes": "Mock Stedi test-mode style response for hackathon demos. No PHI sent.",
}


class StediService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def check_eligibility(
        self,
        *,
        member_id: str = "UHC202649",
        first_name: str = "Jordan",
        last_name: str = "Lee",
        service_type: str = "30",
    ) -> dict[str, Any]:
        if self.settings.use_mock or not self.settings.stedi_api_key:
            return {"mode": "mock", **MOCK_BENEFITS, "memberId": member_id}

        payload = {
            "tradingPartnerServiceId": "87726",
            "provider": {
                "organizationName": "Hackathon Demo Clinic",
                "npi": "1999999984",
            },
            "subscriber": {
                "memberId": member_id,
                "firstName": first_name,
                "lastName": last_name,
            },
            "encounter": {"serviceTypeCodes": [service_type]},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                STEDI_ELIGIBILITY_URL,
                headers={
                    "Authorization": self.settings.stedi_api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            data = r.json() if r.content else {}
            return {
                "mode": "live",
                "status_code": r.status_code,
                "raw": data,
                "summary": _summarize_live(data),
            }

    async def check_text(self, service_hint: str = "urgent telehealth") -> str:
        result = await self.check_eligibility()
        if result.get("mode") == "mock":
            return (
                f"Eligibility ({result['mode']}): {result['payer']} — "
                f"{result['planStatus']}. "
                f"Est. urgent-care copay ${result['copay_urgent_care_usd']}; "
                f"deductible remaining ${result['deductible_remaining_usd']}. "
                f"Suggested for: {service_hint}."
            )
        return f"Eligibility (live): {result.get('summary')} status={result.get('status_code')}"


def _summarize_live(data: dict[str, Any]) -> str:
    # Best-effort parse; Stedi responses vary by payer fixture
    benefits = data.get("benefitsInformation") or data.get("benefits") or []
    plan = data.get("planStatus") or data.get("status") or "see raw"
    return f"plan={plan}; benefit_entries={len(benefits) if isinstance(benefits, list) else 'n/a'}"
