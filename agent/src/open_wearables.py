"""Open Wearables client — unified Whoop / Oura / Fitbit / Garmin / … risk signals.

Docs: https://openwearables.io/docs/api-reference/introduction
Auth: X-Open-Wearables-API-Key (not Bearer)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import Settings, get_settings
from .whoop_client import WhoopClient

# Lowercase provider path names per Open Wearables docs
PROVIDERS = (
    "whoop",
    "oura",
    "fitbit",
    "garmin",
    "polar",
    "suunto",
    "strava",
    "ultrahuman",
    "apple",
)


def _median(values: list[float]) -> float | None:
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def _baseline(nights: list[dict[str, Any]]) -> dict[str, Any]:
    """What normal looks like for this person, not for a population.

    A recovery score of 30 is a red flag against a textbook and unremarkable for someone whose
    median is 32. Population cutoffs are why monitoring produces noise: they fire on constitution
    rather than on change. The median is used over the mean because a fortnight contains
    illnesses, flights and one very bad night, and those should shift the reference point less
    than they shift an average.
    """
    def med(section: str, key: str) -> float | None:
        return _median([(n.get(section) or {}).get(key) for n in nights])

    return {
        "nights": len(nights),
        "recovery_score": med("recovery", "recovery_score"),
        "resting_heart_rate_bpm": med("recovery", "resting_heart_rate_bpm"),
        "avg_hrv_sdnn_ms": med("recovery", "avg_hrv_sdnn_ms"),
        "skin_temp_celsius": med("recovery", "skin_temp_celsius"),
        "duration_minutes": med("sleep", "duration_minutes"),
        "efficiency_percent": med("sleep", "efficiency_percent"),
        "awake_minutes": med("sleep", "awake_minutes"),
        "respiratory_rate": med("sleep", "respiratory_rate"),
    }


# Departures large enough to be worth a clinician's attention, expressed against the patient's
# own median. Each is a deviation, not a cutoff.
_DEVIATIONS: tuple[tuple[str, str, str, float, str], ...] = (
    ("recovery", "recovery_score", "below", 12, "recovery {v} against their usual {b}"),
    ("recovery", "resting_heart_rate_bpm", "above", 6, "resting heart rate {v} against {b}"),
    ("recovery", "avg_hrv_sdnn_ms", "below", 12, "HRV {v} against {b}"),
    ("recovery", "skin_temp_celsius", "above", 0.4, "skin temperature {v} against {b}"),
    ("sleep", "duration_minutes", "below", 75, "slept {v} min against their usual {b}"),
    ("sleep", "efficiency_percent", "below", 6, "sleep efficiency {v}% against {b}%"),
    ("sleep", "awake_minutes", "above", 35, "{v} min awake against their usual {b}"),
    # Respiratory rate is among the steadiest things a strap measures — it varies by a few tenths
    # of a breath night to night — so a rise of more than a breath and a half is a large move,
    # and it tends to arrive early. Nonspecific as to cause, like everything else here.
    ("sleep", "respiratory_rate", "above", 1.5, "breathing {v} a minute against their usual {b}"),
)

# Values that are worth surfacing whatever this patient's baseline is, because they are dangerous
# rather than merely unusual.
_ABSOLUTE: tuple[tuple[str, str, str, float, str], ...] = (
    ("recovery", "resting_heart_rate_bpm", "above", 95, "resting heart rate {v} bpm"),
    ("recovery", "avg_spo2_percent", "below", 92, "oxygen saturation {v}%"),
    ("recovery", "skin_temp_celsius", "above", 36.0, "skin temperature {v} °C"),
)


def _against_baseline(night: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    score = 0

    def fmt(x: float) -> str:
        return str(int(x)) if float(x).is_integer() else str(round(x, 1))

    for section, key, direction, margin, template in _DEVIATIONS:
        value = (night.get(section) or {}).get(key)
        base = baseline.get(key)
        if not isinstance(value, (int, float)) or not isinstance(base, (int, float)):
            continue
        delta = base - value if direction == "below" else value - base
        if delta >= margin:
            score += 1
            reasons.append(template.format(v=fmt(value), b=fmt(base)))

    for section, key, direction, limit, template in _ABSOLUTE:
        value = (night.get(section) or {}).get(key)
        if not isinstance(value, (int, float)):
            continue
        if (value < limit) if direction == "below" else (value > limit):
            score += 2
            reasons.append(template.format(v=fmt(value)))

    # One metric drifting is noise; two moving together on the same night is a pattern.
    level = "high" if score >= 3 else "moderate" if score >= 2 else "low"
    recovery = night.get("recovery") or {}
    sleep = night.get("sleep") or {}
    return {
        "date": night["date"],
        "level": level,
        "score": score,
        "reasons": reasons,
        "surfaced": score >= 2,
        # Carried through for the patient's own chart. A person shown "3 nights surfaced" learns
        # nothing; a person shown the shape of their own fortnight can see it for themselves.
        "recovery_score": recovery.get("recovery_score"),
        "duration_minutes": sleep.get("duration_minutes"),
        "resting_heart_rate_bpm": recovery.get("resting_heart_rate_bpm"),
    }


class OpenWearablesService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base = self.settings.open_wearables_base_url.rstrip("/")
        if not self.base.endswith("/api/v1"):
            # allow http://localhost:8000 or full …/api/v1
            if self.base.endswith("/api"):
                self.base = f"{self.base}/v1"
            else:
                self.base = f"{self.base}/api/v1"

    @property
    def use_mock(self) -> bool:
        if self.settings.use_mock:
            return True
        return not bool(self.settings.open_wearables_api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Open-Wearables-API-Key": self.settings.open_wearables_api_key,
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()

    async def list_providers(self) -> list[str]:
        if self.use_mock:
            return list(PROVIDERS)
        data = await self._get("/oauth/providers")
        if isinstance(data, list):
            return [str(p.get("name") or p) for p in data]
        items = data.get("items") or data.get("providers") or data.get("data") or []
        return [str(p.get("name") or p) for p in items] or list(PROVIDERS)

    async def authorize_url(self, provider: str, user_id: str, redirect_uri: str) -> dict[str, Any]:
        provider = provider.lower()
        if self.use_mock:
            return {
                "authorization_url": (
                    f"https://mock.openwearables.local/oauth/{provider}"
                    f"?user_id={user_id}&redirect_uri={redirect_uri}"
                ),
                "state": "mock-state",
                "provider": provider,
                "mode": "mock",
            }
        data = await self._get(
            f"/oauth/{provider}/authorize",
            params={"user_id": user_id, "redirect_uri": redirect_uri},
        )
        data["provider"] = provider
        data["mode"] = "live"
        return data

    async def recovery_summary(self, user_id: str) -> Any:
        if self.use_mock:
            return {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "source": {"provider": "whoop", "device": None},
                "resting_heart_rate_bpm": 88,
                "avg_hrv_sdnn_ms": 28.0,
                "avg_spo2_percent": 96.0,
                "recovery_score": 32,
            }
        return await self._get(f"/users/{user_id}/summaries/recovery")

    async def sleep_summary(self, user_id: str) -> Any:
        if self.use_mock:
            return {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "source": {"provider": "oura", "device": None},
                "duration_minutes": 320,
                "efficiency_percent": 78.0,
                "avg_hrv_sdnn_ms": 30.0,
                "avg_spo2_percent": 95.5,
            }
        return await self._get(f"/users/{user_id}/summaries/sleep")

    def evaluate_risk(
        self,
        recovery: dict[str, Any] | None,
        sleep: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Rule-based triage signal — not a diagnosis."""
        recovery = recovery or {}
        sleep = sleep or {}
        reasons: list[str] = []
        score = 0

        rhr = recovery.get("resting_heart_rate_bpm")
        hrv = recovery.get("avg_hrv_sdnn_ms") or sleep.get("avg_hrv_sdnn_ms")
        rec = recovery.get("recovery_score")
        sleep_min = sleep.get("duration_minutes")
        skin_temp = recovery.get("skin_temp_celsius")
        efficiency = sleep.get("efficiency_percent")
        awake_min = sleep.get("awake_minutes")
        provider = (recovery.get("source") or sleep.get("source") or {}).get("provider") or "unknown"

        if isinstance(rhr, (int, float)) and rhr >= 85:
            score += 2
            reasons.append(f"elevated resting HR ({rhr} bpm)")
        if isinstance(hrv, (int, float)) and hrv < 35:
            score += 2
            reasons.append(f"low HRV ({round(hrv, 1)} ms)")
        if isinstance(rec, (int, float)) and rec < 40:
            score += 2
            reasons.append(f"low recovery score ({rec})")
        if isinstance(sleep_min, (int, float)) and sleep_min < 360:
            score += 1
            reasons.append(f"short sleep ({sleep_min} min)")
        # Eczema-specific: nocturnal itch shows up as fragmented sleep + warmer skin
        if isinstance(efficiency, (int, float)) and efficiency < 85:
            score += 1
            reasons.append(f"fragmented sleep (efficiency {round(efficiency, 1)}%)")
        if isinstance(awake_min, (int, float)) and awake_min >= 60:
            score += 1
            reasons.append(f"{awake_min} min awake overnight (possible nocturnal symptoms)")
        if isinstance(skin_temp, (int, float)) and skin_temp >= 34.5:
            score += 1
            reasons.append(f"elevated skin temperature ({round(skin_temp, 1)} °C)")

        level = "high" if score >= 4 else "moderate" if score >= 2 else "low"
        triggered = level in {"moderate", "high"}
        # Name only the strap, not the transport: the same evaluation runs whether the data came
        # from the direct Whoop API or an Open Wearables instance, and crediting the wrong one in
        # clinician-facing text is a provenance claim we cannot back up. The snapshot's `source`
        # and `mode` fields carry the transport for anyone who needs it.
        context = (
            f"Wearable risk signal ({level}) from {provider}: "
            + ("; ".join(reasons) if reasons else "within baseline")
            + ". Not a diagnosis — consider history-aware voice check-in."
        )
        return {
            "triggered": triggered,
            "level": level,
            "score": score,
            "reasons": reasons,
            "provider": provider,
            "context": context,
            "recovery": recovery,
            "sleep": sleep,
        }

    async def monitoring_window(self, days: int = 14) -> dict[str, Any]:
        """Review every night, surface only the ones that cross the line.

        The failure mode of passive monitoring is not missing data, it is sending all of it: a
        clinician who receives fourteen nightly summaries stops reading the fourteenth, and the
        one that mattered arrives in a queue nobody opens. So the window is evaluated here and
        only the nights that crossed a threshold are proposed for the chart. The suppressed count
        stays visible — a filter you cannot see the size of is indistinguishable from data loss.
        """
        whoop = WhoopClient(self.settings)
        if not whoop.connected:
            return {"available": False, "reason": "no wearable connected"}

        nights = await whoop.recent_days(days)
        baseline = _baseline(nights)
        evaluated = [_against_baseline(n, baseline) for n in nights]

        surfaced = [e for e in evaluated if e["surfaced"]]
        return {
            "available": True,
            "provider": "whoop",
            "baseline": baseline,
            "reviewed": len(evaluated),
            "surfaced": len(surfaced),
            "suppressed": len(evaluated) - len(surfaced),
            "nights": evaluated,
            "surfaced_nights": surfaced,
            # Written for the clinician, who needs to know the size of what they are not seeing.
            "context": (
                f"{len(evaluated)} nights reviewed from Whoop against this patient's own "
                f"baseline (recovery {baseline.get('recovery_score')}, sleep "
                f"{baseline.get('duration_minutes')} min). {len(surfaced)} departed from it; "
                f"{len(evaluated) - len(surfaced)} did not and were not charted. "
                # Departures in sleep, temperature or heart rate are nonspecific. Stating the
                # limit next to the number stops the number being read as a finding, and this
                # must never displace a symptom screen.
                "Supporting context only — nonspecific, and not a test for any condition."
            ),
        }

    async def risk_snapshot(self, user_id: str | None = None) -> dict[str, Any]:
        uid = user_id or self.settings.open_wearables_user_id or "mock-user"

        # A real connected Whoop strap wins over Open Wearables / mock summaries
        whoop = WhoopClient(self.settings)
        if whoop.connected:
            summaries = await whoop.summaries()
            out = self.evaluate_risk(summaries["recovery"], summaries["sleep"])
            out["user_id"] = uid
            out["mode"] = "live-whoop"
            out["source"] = "whoop-api-v2"
            out["as_of"] = datetime.now(timezone.utc).isoformat()
            return out

        recovery = await self.recovery_summary(uid)
        sleep = await self.sleep_summary(uid)
        # Normalize list envelopes if API wraps data
        if isinstance(recovery, dict) and "data" in recovery and isinstance(recovery["data"], list):
            recovery = recovery["data"][0] if recovery["data"] else {}
        if isinstance(sleep, dict) and "data" in sleep and isinstance(sleep["data"], list):
            sleep = sleep["data"][0] if sleep["data"] else {}
        out = self.evaluate_risk(
            recovery if isinstance(recovery, dict) else {},
            sleep if isinstance(sleep, dict) else {},
        )
        out["user_id"] = uid
        out["mode"] = "mock" if self.use_mock else "live"
        out["as_of"] = datetime.now(timezone.utc).isoformat()
        # Lookback hint for demos
        out["window_start"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        return out

    async def risk_context_text(self, user_id: str | None = None) -> str:
        snap = await self.risk_snapshot(user_id)
        return snap["context"]
