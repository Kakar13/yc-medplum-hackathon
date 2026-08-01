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

# Aetna. Test mode matches fixtures exactly, so these values are not arbitrary.
TEST_PAYER_ID = "60054"
TEST_SUBSCRIBER = {"firstName": "John", "lastName": "Doe", "memberId": "AETNA9wcSu"}
TEST_DEPENDENT = {"firstName": "Jordan", "lastName": "Doe", "dateOfBirth": "20010714"}

# Dental runs on a separate payer and service type code (35, not 30) with its own fixture — a
# medical eligibility check tells a patient nothing about what a crown will cost them. Cigna
# dental fixture from the same Stedi mock-request docs.
DENTAL_PAYER_ID = "62308"
DENTAL_SUBSCRIBER = {
    "firstName": "Jaguar",
    "lastName": "Dent",
    "dateOfBirth": "19960505",
    "memberId": "U3141592653",
}

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
        member_id: str = TEST_SUBSCRIBER["memberId"],
        first_name: str = TEST_SUBSCRIBER["firstName"],
        last_name: str = TEST_SUBSCRIBER["lastName"],
        service_type: str = "30",
    ) -> dict[str, Any]:
        if self.settings.use_mock or not self.settings.stedi_api_key:
            return {"mode": "mock", **MOCK_BENEFITS, "memberId": member_id}

        # Stedi test mode only accepts published fixtures verbatim — any other name, member ID
        # or birth date returns an AAA error rather than benefits. This is the Aetna
        # subscriber+dependent fixture from Stedi's own docs:
        # https://www.stedi.com/docs/healthcare/api-reference/mock-requests-eligibility-checks
        if service_type == "35":
            # Dental is a different payer, a different member, and no dependent — reusing the
            # medical fixture here just returns an AAA error.
            payload = {
                "tradingPartnerServiceId": DENTAL_PAYER_ID,
                "provider": {"organizationName": "One", "npi": "1999999984"},
                "subscriber": dict(DENTAL_SUBSCRIBER),
                "encounter": {"serviceTypeCodes": ["35"]},
            }
        else:
            payload = {
                "tradingPartnerServiceId": TEST_PAYER_ID,
                "provider": {
                    "organizationName": "Provider Name",
                    "npi": "1999999984",
                },
                "subscriber": {
                    "memberId": member_id,
                    "firstName": first_name,
                    "lastName": last_name,
                },
                "dependents": [dict(TEST_DEPENDENT)],
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
        # Route dental work to the dental benefit. A medical check would come back "active
        # coverage" and tell the patient nothing about what a crown costs them.
        dental_words = (
            "dental", "dentist", "tooth", "teeth", "crown", "root canal", "filling",
            "composite", "extraction", "hygien", "cleaning", "perio", "molar",
        )
        service_type = "35" if any(w in service_hint.lower() for w in dental_words) else "30"
        result = await self.check_eligibility(service_type=service_type)
        if result.get("mode") == "mock":
            return (
                f"Eligibility ({result['mode']}): {result['payer']} — "
                f"{result['planStatus']}. "
                f"Est. urgent-care copay ${result['copay_urgent_care_usd']}; "
                f"deductible remaining ${result['deductible_remaining_usd']}. "
                f"Suggested for: {service_hint}."
            )
        s = result.get("summary") or {}
        if s.get("errors") and not s.get("benefit_entries"):
            first = s["errors"][0]
            return (
                f"Eligibility (live, {result.get('status_code')}): could not verify — "
                f"{first.get('description')} (AAA {first.get('code')}). "
                f"Coverage needs to be confirmed at the front desk."
            )
        bits = [
            f"{s.get('payer') or 'payer'} — "
            f"{'active coverage' if s.get('active_coverage') else 'coverage status unclear'}"
        ]
        if c := s.get("headline_copay"):
            bits.append(f"${c['amount_usd']:.0f} copay for an {c['service']}")
        if d := s.get("deductible_remaining"):
            bits.append(f"${d['amount_usd']:.0f} deductible remaining")
        if s.get("coinsurance"):
            bits.append(f"coinsurance {float(s['coinsurance'][0]['percent']) * 100:.0f}%")
        return f"Eligibility (live): {'; '.join(bits)}. Suggested for: {service_hint}."


# X12 service type codes we surface to patients. Full list is large; these are the ones that
# actually answer "what will this visit cost me".
SERVICE_TYPE_LABELS = {
    "1": "medical care",
    "30": "health benefit plan coverage",
    "33": "chiropractic",
    "35": "dental care",
    "47": "hospital",
    "48": "hospital inpatient",
    "50": "hospital outpatient",
    "86": "emergency services",
    "88": "pharmacy",
    "98": "office visit",
    "AL": "vision",
    "MH": "mental health",
    "UC": "urgent care",
}

# Preference order when picking the single most quotable copay for a pre-visit estimate.
PREFERRED_SERVICE_TYPES = ("98", "UC", "1", "30", "86")


def _label_service(codes: list[str] | None, fallback: str | None) -> str:
    for c in codes or []:
        if c in SERVICE_TYPE_LABELS:
            return SERVICE_TYPE_LABELS[c]
    return ", ".join(codes or []) or fallback or "plan"


def _best(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the entry a patient would care about most, not just the first one returned."""
    for stc in PREFERRED_SERVICE_TYPES:
        for item in items:
            if stc in (item.get("codes") or []):
                return item
    return items[0] if items else None


def _money(entry: dict[str, Any]) -> float | None:
    raw = entry.get("benefitAmount")
    try:
        return float(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _summarize_live(data: dict[str, Any]) -> dict[str, Any]:
    """Reduce a 271 benefits response to the few numbers a patient actually asked for.

    Payers vary in how they populate these entries, so every field is optional and the raw
    response stays attached for the clinician view.
    """
    errors = [
        {"code": e.get("code"), "description": e.get("description")}
        for e in (data.get("errors") or [])
    ]
    entries = data.get("benefitsInformation") or []
    if not isinstance(entries, list):
        entries = []

    payer = (data.get("payer") or {}).get("name")
    active = any(e.get("code") == "1" for e in entries)
    copays: list[dict[str, Any]] = []
    deductibles: list[dict[str, Any]] = []
    coinsurance: list[dict[str, Any]] = []

    for e in entries:
        code = e.get("code")
        amount = _money(e)
        codes = e.get("serviceTypeCodes") or []
        label = _label_service(codes, e.get("name"))
        level = e.get("coverageLevel") or e.get("coverageLevelCode") or ""
        period = e.get("timeQualifier") or ""
        base = {"service": label, "codes": codes}
        if code == "B" and amount is not None:
            copays.append({**base, "amount_usd": amount, "network": e.get("inPlanNetworkIndicator")})
        elif code == "C" and amount is not None:
            deductibles.append({**base, "amount_usd": amount, "period": period, "level": level})
        elif code == "A" and e.get("benefitPercent") is not None:
            coinsurance.append({**base, "percent": e.get("benefitPercent")})

    # Individual remaining deductible is the number that changes what a patient pays today.
    remaining = [
        d
        for d in deductibles
        if d.get("period") == "Remaining" and d.get("level") == "Individual"
    ]

    return {
        "payer": payer,
        "active_coverage": active,
        "benefit_entries": len(entries),
        "copays": copays[:6],
        "deductibles": deductibles[:6],
        "coinsurance": coinsurance[:4],
        "headline_copay": _best(copays),
        "deductible_remaining": _best(remaining) or _best(deductibles),
        "errors": errors,
    }
