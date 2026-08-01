#!/usr/bin/env python3
"""Verify the Whoop connection: config → OAuth state → real recovery/sleep → risk → FHIR.

Usage:
    python scripts/whoop_check.py [api_base]

Prints the authorize URL when the app is configured but the strap is not linked yet.
"""

from __future__ import annotations

import json
import sys

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"


def main() -> int:
    c = httpx.Client(base_url=API, timeout=60.0)

    try:
        status = c.get("/wearables/whoop/status").json()
    except httpx.ConnectError:
        print(f"API not reachable at {API} — start it with:")
        print("  cd agent && source .venv/bin/activate && uvicorn src.api:app --reload --port 8080")
        return 1
    print("configured:", status["configured"], "| connected:", status["connected"])
    print("redirect_uri:", status["redirect_uri"])

    if not status["configured"]:
        print("\nSet WHOOP_CLIENT_ID / WHOOP_CLIENT_SECRET in agent/.env, restart the API, rerun.")
        return 1

    if not status["connected"]:
        auth = c.get("/wearables/whoop/authorize").json()
        print("\nOpen this URL in a browser and authorize, then rerun:")
        print(auth["authorization_url"])
        return 2

    print("profile:", json.dumps(status.get("user") or {}))

    summaries = c.get("/wearables/whoop/summaries").json()
    print("\nrecovery:", json.dumps(summaries["recovery"]))
    print("sleep:", json.dumps(summaries["sleep"]))

    risk = c.get("/wearables/risk").json()
    print("\nrisk:", risk["level"], f"(score {risk['score']}, mode {risk['mode']})")
    for reason in risk.get("reasons") or ["within baseline"]:
        print("  -", reason)

    charted = c.post("/wearables/to-chart", json={}).json()
    print(
        "\ncharted:",
        len(charted.get("observation_ids") or []),
        "Observations →",
        f"Encounter/{charted['encounter_id']}",
        f"({charted.get('mode', 'mock')})",
    )
    print("chart URL:", f"http://localhost:5173/chart/{charted['encounter_id']}")
    print("\nOK Whoop connected end-to-end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
