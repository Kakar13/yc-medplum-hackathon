"""One-time HMAC capture tokens for secure phone photo upload.

Patient never receives Medplum client secrets — only a short-lived app URL.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import Settings, get_settings

STORE_PATH = Path(__file__).resolve().parents[1] / "data" / ".capture_tokens.json"
TTL_SECONDS = 15 * 60


@dataclass
class CaptureLink:
    token: str
    patient_id: str
    encounter_id: str
    binary_id: str
    content_type: str
    upload_url: str
    created_at: float
    expires_at: float
    used: bool = False
    media_id: str | None = None
    document_reference_id: str | None = None
    patient_display: str = "Patient"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaptureLink:
        return cls(**data)


class CaptureLinkStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._secret = (
            self.settings.capture_token_secret
            or self.settings.medplum_client_secret
            or "flarecheck-dev-secret"
        ).encode()
        self._links: dict[str, CaptureLink] = {}
        self._load()

    def _load(self) -> None:
        if not STORE_PATH.exists():
            return
        try:
            raw = json.loads(STORE_PATH.read_text())
            for token, data in raw.items():
                self._links[token] = CaptureLink.from_dict(data)
        except Exception:
            self._links = {}

    def _persist(self) -> None:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text(
            json.dumps({t: link.to_dict() for t, link in self._links.items()}, indent=2)
        )

    def _sign(self, token: str) -> str:
        return hmac.new(self._secret, token.encode(), hashlib.sha256).hexdigest()[:16]

    def public_url(self, token: str) -> str:
        base = self.settings.public_app_url.rstrip("/")
        sig = self._sign(token)
        return f"{base}/capture/{token}?s={sig}"

    def issue(
        self,
        *,
        patient_id: str,
        encounter_id: str,
        binary_id: str,
        upload_url: str,
        content_type: str = "image/jpeg",
        patient_display: str = "Patient",
        ttl_seconds: int = TTL_SECONDS,
    ) -> CaptureLink:
        token = secrets.token_urlsafe(24)
        now = time.time()
        link = CaptureLink(
            token=token,
            patient_id=patient_id,
            encounter_id=encounter_id,
            binary_id=binary_id,
            content_type=content_type,
            upload_url=upload_url,
            created_at=now,
            expires_at=now + ttl_seconds,
            patient_display=patient_display,
        )
        self._links[token] = link
        self._persist()
        return link

    def get(self, token: str, sig: str | None = None) -> CaptureLink | None:
        link = self._links.get(token)
        if not link:
            return None
        if sig is not None and not hmac.compare_digest(self._sign(token), sig):
            return None
        if link.used:
            return None
        if time.time() > link.expires_at:
            return None
        return link

    def peek(self, token: str) -> CaptureLink | None:
        return self._links.get(token)

    def mark_complete(
        self,
        token: str,
        *,
        media_id: str | None = None,
        document_reference_id: str | None = None,
    ) -> CaptureLink | None:
        link = self._links.get(token)
        if not link or link.used or time.time() > link.expires_at:
            return None
        link.used = True
        link.media_id = media_id
        link.document_reference_id = document_reference_id
        self._persist()
        return link


_store: CaptureLinkStore | None = None


def get_capture_store() -> CaptureLinkStore:
    global _store
    if _store is None:
        _store = CaptureLinkStore()
    return _store
