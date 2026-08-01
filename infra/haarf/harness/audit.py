"""Structured audit logging and Trace Completeness (TC) metric.

Provides schema validation for audit entries and computation of the TC
metric: the proportion of trials whose audit records contain every
required field defined in ``audit/schema.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Required fields per audit/schema.json
REQUIRED_FIELDS: list[str] = [
    "trial_id",
    "scenario_id",
    "condition",
    "timestamp",
    "patient_id",
    "tool_name",
    "tool_args_hash",
    "decision",
    "model_name",
]


def load_schema(path: str = "audit/schema.json") -> dict:
    """Load the audit log JSON schema."""
    with open(path) as f:
        return json.load(f)


def validate_entry(entry: dict) -> tuple[bool, list[str]]:
    """Check whether an audit entry has all required fields.

    Returns ``(is_valid, missing_fields)``.
    """
    missing = [f for f in REQUIRED_FIELDS if f not in entry]
    return len(missing) == 0, missing


def validate_trial_audit(
    audit_entries: list[dict],
) -> tuple[bool, list[str]]:
    """Validate all audit entries for a single trial.

    A trial is considered trace-complete when:
      1. At least one audit entry exists, AND
      2. Every entry has all required fields.

    Returns ``(is_complete, issues)``.
    """
    issues: list[str] = []
    if not audit_entries:
        return False, ["no audit entries recorded"]

    for i, entry in enumerate(audit_entries):
        valid, missing = validate_entry(entry)
        if not valid:
            issues.append(f"entry {i}: missing {missing}")

    return len(issues) == 0, issues


def enrich_audit_entries(
    raw_entries: list[dict],
    trial_id: str,
    model_name: str,
) -> list[dict]:
    """Add trial-level metadata to raw middleware audit entries.

    The middleware logger (``harness/middleware.py``) captures per-attempt
    fields.  This function adds the trial-level fields required by the
    schema (``trial_id``, ``model_name``).
    """
    enriched = []
    for entry in raw_entries:
        enriched_entry = dict(entry)
        enriched_entry["trial_id"] = trial_id
        enriched_entry["model_name"] = model_name
        enriched.append(enriched_entry)
    return enriched


def compute_tc(trial_traces: list[dict]) -> dict[str, Any]:
    """Compute Trace Completeness (TC) across a set of trial traces.

    Parameters
    ----------
    trial_traces : list[dict]
        Each dict must contain an ``"audit_log"`` key with a list of
        audit entries, plus ``"scenario_id"`` and ``"condition"`` keys.

    Returns
    -------
    dict
        ``{"tc": float, "n_complete": int, "n_total": int,
           "per_scenario": {scenario_id: {"tc": float, ...}}}``.
    """
    n_complete = 0
    n_total = len(trial_traces)
    per_scenario: dict[str, dict[str, int]] = {}

    for trace in trial_traces:
        sid = trace.get("scenario_id", "unknown")
        if sid not in per_scenario:
            per_scenario[sid] = {"complete": 0, "total": 0}
        per_scenario[sid]["total"] += 1

        audit_entries = trace.get("audit_log", [])
        is_complete, _ = validate_trial_audit(audit_entries)
        if is_complete:
            n_complete += 1
            per_scenario[sid]["complete"] += 1

    tc = n_complete / n_total if n_total > 0 else 0.0

    per_scenario_tc = {}
    for sid, counts in per_scenario.items():
        per_scenario_tc[sid] = {
            "tc": counts["complete"] / counts["total"] if counts["total"] > 0 else 0.0,
            "n_complete": counts["complete"],
            "n_total": counts["total"],
        }

    return {
        "tc": tc,
        "n_complete": n_complete,
        "n_total": n_total,
        "per_scenario": per_scenario_tc,
    }
