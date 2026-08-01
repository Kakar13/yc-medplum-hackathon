"""Direct Whoop API v2 client — OAuth 2.0 + recovery / sleep / cycle.

Used when a real Whoop membership is connected (no Open Wearables instance needed).
Whoop docs: https://developer.whoop.com/docs/developing/getting-started
Dashboard:  https://developer-dashboard.whoop.com/

Normalizes into the same shape OpenWearablesService produces so
`OpenWearablesService.evaluate_risk` and the FlareCheck agent stay unchanged.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Settings, get_settings

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer/v2"

TOKEN_PATH = Path(__file__).resolve().parent.parent / ".whoop_tokens.json"


class WhoopNotConnected(RuntimeError):
    pass


class WhoopClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._states: dict[str, str] = {}

    @property
    def configured(self) -> bool:
        return bool(self.settings.whoop_client_id and self.settings.whoop_client_secret)

    # --- token storage (single demo user; file-backed so uvicorn reload survives) ---

    def _load_tokens(self) -> dict[str, Any]:
        if not TOKEN_PATH.exists():
            return {}
        try:
            return json.loads(TOKEN_PATH.read_text())
        except Exception:
            return {}

    def _save_tokens(self, tokens: dict[str, Any]) -> None:
        TOKEN_PATH.write_text(json.dumps(tokens, indent=2))
        TOKEN_PATH.chmod(0o600)

    @property
    def connected(self) -> bool:
        return bool(self._load_tokens().get("access_token"))

    def status(self) -> dict[str, Any]:
        tokens = self._load_tokens()
        return {
            "configured": self.configured,
            "connected": bool(tokens.get("access_token")),
            "scope": tokens.get("scope"),
            "expires_at": tokens.get("expires_at"),
            "connected_at": tokens.get("connected_at"),
            "user": tokens.get("profile"),
            "redirect_uri": self.settings.whoop_redirect_uri,
        }

    def disconnect(self) -> None:
        TOKEN_PATH.unlink(missing_ok=True)

    # --- OAuth ---

    def authorize_url(self) -> dict[str, Any]:
        if not self.configured:
            raise WhoopNotConnected(
                "WHOOP_CLIENT_ID / WHOOP_CLIENT_SECRET not set — create an app at "
                "https://developer-dashboard.whoop.com/"
            )
        state = secrets.token_urlsafe(16)
        self._states[state] = datetime.now(timezone.utc).isoformat()
        params = {
            "client_id": self.settings.whoop_client_id,
            "redirect_uri": self.settings.whoop_redirect_uri,
            "response_type": "code",
            "scope": self.settings.whoop_scope,
            "state": state,
        }
        url = str(httpx.URL(AUTH_URL, params=params))
        return {"authorization_url": url, "state": state}

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.settings.whoop_client_id,
            "client_secret": self.settings.whoop_client_secret,
            "redirect_uri": self.settings.whoop_redirect_uri,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(TOKEN_URL, data=data)
            r.raise_for_status()
            payload = r.json()
        tokens = self._store_token_payload(payload)
        try:
            tokens["profile"] = await self.profile()
            self._save_tokens(tokens)
        except Exception:
            pass
        return self.status()

    def _store_token_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        expires_in = int(payload.get("expires_in") or 3600)
        tokens = {
            "access_token": payload.get("access_token"),
            "refresh_token": payload.get("refresh_token") or self._load_tokens().get("refresh_token"),
            "scope": payload.get("scope"),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
            ).isoformat(),
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = self._load_tokens()
        if existing.get("profile"):
            tokens["profile"] = existing["profile"]
        self._save_tokens(tokens)
        return tokens

    async def _refresh(self, refresh_token: str) -> str:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.whoop_client_id,
            "client_secret": self.settings.whoop_client_secret,
            "scope": "offline",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(TOKEN_URL, data=data)
            r.raise_for_status()
            payload = r.json()
        return str(self._store_token_payload(payload)["access_token"])

    async def _access_token(self) -> str:
        tokens = self._load_tokens()
        token = tokens.get("access_token")
        if not token:
            raise WhoopNotConnected("Whoop not connected — run the OAuth flow first")
        expires_at = tokens.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
            if tokens.get("refresh_token"):
                return await self._refresh(str(tokens["refresh_token"]))
        return str(token)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            if r.status_code == 401:
                tokens = self._load_tokens()
                if tokens.get("refresh_token"):
                    token = await self._refresh(str(tokens["refresh_token"]))
                    r = await client.get(
                        f"{API_BASE}{path}",
                        headers={"Authorization": f"Bearer {token}"},
                        params=params,
                    )
            r.raise_for_status()
            return r.json()

    # --- data ---

    async def profile(self) -> dict[str, Any]:
        return await self._get("/user/profile/basic")

    async def latest_recovery(self) -> dict[str, Any]:
        data = await self._get("/recovery", {"limit": 1})
        records = data.get("records") or []
        return records[0] if records else {}

    async def latest_sleep(self) -> dict[str, Any]:
        data = await self._get("/activity/sleep", {"limit": 1})
        records = data.get("records") or []
        return records[0] if records else {}

    # --- normalization to the FlareCheck / Open Wearables summary shape ---

    def normalize_recovery(self, record: dict[str, Any]) -> dict[str, Any]:
        score = record.get("score") or {}
        created = record.get("created_at") or datetime.now(timezone.utc).isoformat()
        return {
            "date": created[:10],
            "source": {"provider": "whoop", "device": "whoop-strap"},
            "resting_heart_rate_bpm": score.get("resting_heart_rate"),
            "avg_hrv_sdnn_ms": score.get("hrv_rmssd_milli"),
            "avg_spo2_percent": score.get("spo2_percentage"),
            "recovery_score": score.get("recovery_score"),
            "skin_temp_celsius": score.get("skin_temp_celsius"),
            "calibrating": score.get("user_calibrating"),
            "cycle_id": record.get("cycle_id"),
        }

    def normalize_sleep(self, record: dict[str, Any]) -> dict[str, Any]:
        score = record.get("score") or {}
        stages = score.get("stage_summary") or {}
        in_bed_milli = stages.get("total_in_bed_time_milli") or 0
        awake_milli = stages.get("total_awake_time_milli") or 0
        asleep_minutes = max(0, round((in_bed_milli - awake_milli) / 60000)) or None
        start = record.get("start") or datetime.now(timezone.utc).isoformat()
        return {
            "date": start[:10],
            "source": {"provider": "whoop", "device": "whoop-strap"},
            "duration_minutes": asleep_minutes,
            "efficiency_percent": score.get("sleep_efficiency_percentage"),
            "awake_minutes": round(awake_milli / 60000) if awake_milli else None,
            "disturbances": stages.get("disturbance_count"),
            "respiratory_rate": score.get("respiratory_rate"),
            "sleep_performance_percent": score.get("sleep_performance_percentage"),
            "nap": record.get("nap"),
            "sleep_id": record.get("id"),
        }

    async def summaries(self) -> dict[str, Any]:
        recovery_raw = await self.latest_recovery()
        sleep_raw = await self.latest_sleep()
        return {
            "recovery": self.normalize_recovery(recovery_raw),
            "sleep": self.normalize_sleep(sleep_raw),
            "raw": {"recovery": recovery_raw, "sleep": sleep_raw},
        }
