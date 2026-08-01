"""Patient-scoped capability tokens for clinical agents.

The premise: **the subject of care must be a property of the agent's authorization,
never an argument the model chooses.** Every clinical agent today authenticates as an
application with broad access and then names a patient in free-text tool arguments,
which makes patient identity untrusted model output.

A capability binds one agent session to exactly one Patient, one purpose of use, and a
tool allowlist, for a short window. Tool calls never carry a patient identifier — the
gateway injects the subject server-side. A call that references any other patient is
denied and audited rather than silently executed against the wrong chart.

Standards alignment:
  - SMART App Launch 2.0 launch context `patient=<id>` (compartment restriction)
    https://hl7.org/fhir/smart-app-launch/scopes-and-launch-context.html
  - FHIR Patient compartment
    https://hl7.org/fhir/R4/compartmentdefinition-patient.html
  - Medplum enforces `patient=` as a compartment scope, so denial is server-side too
    infra/medplum/packages/docs/docs/access/smart-scopes.md

This closes the gap measured by HAARF RT-4 (wrong-patient action), where the published
framework's own middleware leaves pass rates at 6% [95% CI 0.02-0.16] because its five
layers contain no patient-identity gate, and its contraindication check validates orders
against the *session* patient's allergies while the order names a different MRN.
https://github.com/Task-force-for-AI-agents-in-Healthcare/haarf
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from .config import Settings, get_settings

# Tool argument names that would (re)introduce patient identity as model output
PATIENT_ARG_KEYS = {
    "patient",
    "patient_id",
    "patientid",
    "subject",
    "subject_id",
    "mrn",
    "medical_record_number",
    "member_id",
    "patient_reference",
}

# Identifier shapes we treat as "names a specific patient": MRN-like and FHIR references
_IDENTIFIER_PATTERNS = (
    re.compile(r"\bPatient/([A-Za-z0-9\-\.]{1,64})\b"),
    re.compile(r"\b((?:SYN|MRN|PT)-[A-Za-z0-9]{2,})\b", re.IGNORECASE),
)

DEFAULT_TTL_SECONDS = 30 * 60


class CapabilityError(RuntimeError):
    """Raised when no capability is active or the token is invalid/expired."""


@dataclass
class Capability:
    token: str
    patient_id: str
    encounter_id: str | None
    purpose_of_use: str
    tools: tuple[str, ...]
    actor: str
    on_behalf_of: str | None
    issued_at: float
    expires_at: float
    # Identifiers that legitimately denote the bound patient (id, MRN, references)
    aliases: set[str] = field(default_factory=set)

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    def denotes(self, identifier: str) -> bool:
        candidate = identifier.strip()
        if not candidate:
            return False
        if candidate == self.patient_id or candidate == f"Patient/{self.patient_id}":
            return True
        return candidate.lower() in {a.lower() for a in self.aliases}

    def public(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "patient_id": self.patient_id,
            "encounter_id": self.encounter_id,
            "purpose_of_use": self.purpose_of_use,
            "tools": list(self.tools),
            "actor": self.actor,
            "on_behalf_of": self.on_behalf_of,
            "expires_at": self.expires_at,
            "expires_in_seconds": max(0, int(self.expires_at - time.time())),
            "smart_scope": f"patient={self.patient_id}",
        }


@dataclass
class Decision:
    allowed: bool
    reason: str
    control: str
    tool: str
    requested_patient: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "decision": "allow" if self.allowed else "deny",
            "reason": self.reason,
            "control": self.control,
            "tool": self.tool,
            "requested_patient": self.requested_patient,
        }


class CapabilityGateway:
    """Issues capabilities and adjudicates every tool call against the bound patient."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._active: Capability | None = None
        self._ledger: list[dict[str, Any]] = []
        self._audit_sink = None
        # When False the gateway observes and audits but does not block — the comparator
        # condition for measuring what enforcement actually prevents.
        self.enforcing = True

    # --- issuance ---

    def _sign(self, nonce: str, patient_id: str) -> str:
        secret = (
            self.settings.capability_token_secret
            or self.settings.capture_token_secret
            or "dev-only-capability-secret"
        )
        return hmac.new(
            secret.encode(), f"{nonce}:{patient_id}".encode(), hashlib.sha256
        ).hexdigest()[:32]

    def issue(
        self,
        *,
        patient_id: str,
        encounter_id: str | None = None,
        purpose_of_use: str = "TREAT",
        tools: tuple[str, ...] | list[str] = (),
        actor: str = "Device/preflight-intake-agent",
        on_behalf_of: str | None = None,
        aliases: set[str] | None = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> Capability:
        nonce = secrets.token_urlsafe(12)
        now = time.time()
        cap = Capability(
            token=f"{nonce}.{self._sign(nonce, patient_id)}",
            patient_id=patient_id,
            encounter_id=encounter_id,
            purpose_of_use=purpose_of_use,
            tools=tuple(tools),
            actor=actor,
            on_behalf_of=on_behalf_of,
            issued_at=now,
            expires_at=now + ttl_seconds,
            aliases=set(aliases or set()),
        )
        self._active = cap
        self._record(
            Decision(True, f"Capability issued for Patient/{patient_id}", "C5.1", "issue_capability"),
            extra={"purpose_of_use": purpose_of_use, "ttl_seconds": ttl_seconds},
        )
        return cap

    def revoke(self) -> None:
        if self._active:
            self._record(
                Decision(True, "Capability revoked", "C5.1", "revoke_capability")
            )
        self._active = None

    @property
    def active(self) -> Capability | None:
        if self._active and self._active.expired:
            return None
        return self._active

    def require(self) -> Capability:
        cap = self.active
        if cap is None:
            raise CapabilityError(
                "No active patient capability — an agent may not touch clinical data "
                "without being bound to a specific patient"
            )
        return cap

    def subject_of_care(self) -> str:
        """The only sanctioned way for a tool to learn which patient it is acting on."""
        return self.require().patient_id

    def bind_encounter(self, encounter_id: str) -> None:
        cap = self.active
        if cap:
            cap.encounter_id = encounter_id

    # --- adjudication ---

    def referenced_patients(self, args: dict[str, Any] | None) -> list[str]:
        """Every patient identifier that appears anywhere in a tool call."""
        found: list[str] = []
        if not args:
            return found

        def walk(node: Any, key: str | None = None) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, str(k))
            elif isinstance(node, (list, tuple)):
                for v in node:
                    walk(v, key)
            elif isinstance(node, str):
                if key and key.lower().replace("-", "_") in PATIENT_ARG_KEYS and node.strip():
                    found.append(node.strip())
                for pattern in _IDENTIFIER_PATTERNS:
                    found.extend(m.group(1) for m in pattern.finditer(node))
            elif node is not None and key:
                if key.lower().replace("-", "_") in PATIENT_ARG_KEYS:
                    found.append(str(node))

        walk(args)
        # de-dupe, preserve order
        seen: set[str] = set()
        unique: list[str] = []
        for f in found:
            if f not in seen:
                seen.add(f)
                unique.append(f)
        return unique

    def adjudicate(self, tool: str, args: dict[str, Any] | None = None) -> Decision:
        cap = self.active
        if cap is None:
            return self._record(
                Decision(
                    False,
                    "No active capability — agent is not bound to any patient",
                    "C5.1 agent-registration",
                    tool,
                )
            )

        if cap.tools and tool not in cap.tools:
            return self._record(
                Decision(
                    False,
                    f"Tool '{tool}' is outside the capability's granted scope {sorted(cap.tools)}",
                    "C8.1 tool-authorization",
                    tool,
                )
            )

        for identifier in self.referenced_patients(args):
            if not cap.denotes(identifier):
                return self._record(
                    Decision(
                        False,
                        (
                            f"Capability is bound to Patient/{cap.patient_id}; this call "
                            f"referenced '{identifier}'. The subject of care cannot be "
                            f"chosen by the model."
                        ),
                        "PATIENT-BINDING (HAARF RT-4 gap)",
                        tool,
                        requested_patient=identifier,
                    )
                )

        return self._record(
            Decision(
                True,
                f"Allowed within Patient/{cap.patient_id} compartment",
                "C8.1 tool-authorization",
                tool,
            )
        )

    # --- audit ---

    def set_audit_sink(self, sink) -> None:
        """Attach a MedplumService so decisions also persist as FHIR AuditEvent."""
        self._audit_sink = sink

    def _record(self, decision: Decision, extra: dict[str, Any] | None = None) -> Decision:
        cap = self._active
        # Observe-only mode still records what *would* have been denied
        would_deny = not decision.allowed
        if would_deny and not self.enforcing:
            decision = Decision(
                True,
                f"OBSERVED (not enforced): {decision.reason}",
                decision.control,
                decision.tool,
                decision.requested_patient,
            )
        entry = {
            "enforcing": self.enforcing,
            "would_deny": would_deny,
            "at": time.time(),
            "bound_patient": cap.patient_id if cap else None,
            "encounter_id": cap.encounter_id if cap else None,
            "purpose_of_use": cap.purpose_of_use if cap else None,
            "actor": cap.actor if cap else "unbound",
            **decision.public(),
            **(extra or {}),
        }
        self._ledger.append(entry)
        if self._audit_sink is not None:
            try:
                self._audit_sink.write_audit_event(entry)
            except Exception:
                pass
        return decision

    def ledger(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._ledger[-limit:]

    def reset_ledger(self) -> None:
        self._ledger.clear()

    def stats(self) -> dict[str, Any]:
        flagged = [e for e in self._ledger if e.get("would_deny")]
        crossings = [e for e in flagged if e.get("requested_patient")]
        blocked = [e for e in flagged if not e["allowed"]]
        return {
            "total_decisions": len(self._ledger),
            "flagged": len(flagged),
            "blocked": len(blocked),
            "patient_boundary_events": len(crossings),
            "audited": len(self._ledger),
            "enforcing": self.enforcing,
        }


_gateway: CapabilityGateway | None = None


def get_gateway() -> CapabilityGateway:
    global _gateway
    if _gateway is None:
        _gateway = CapabilityGateway()
    return _gateway
