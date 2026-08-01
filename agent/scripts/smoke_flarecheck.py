#!/usr/bin/env python3
"""End-to-end smoke: session → eczema turn → capture link → upload JPEG → chart."""

from __future__ import annotations

import io
import sys

import httpx

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"


def main() -> None:
    c = httpx.Client(base_url=API, timeout=60.0)
    health = c.get("/health").json()
    print("health", health)

    session = c.post(
        "/session/start",
        json={"reason": "Flare check-in — eczema / rash"},
    ).json()
    print("session", session["patient_id"], session["encounter_id"], session["mode"])

    turn = c.post(
        "/turn",
        json={
            "message": "My eczema on my elbows is flaring and I can't sleep",
            "thread_id": "smoke-flare",
        },
    ).json()
    print("reply", (turn.get("reply") or "")[:180], "...")

    link = c.post(
        "/capture-links",
        json={
            "patient_id": session["patient_id"],
            "encounter_id": session["encounter_id"],
        },
    ).json()
    print("capture", link["url"])
    token = link["token"]

    # Minimal valid-ish JPEG (1x1)
    jpeg = bytes(
        [
            0xFF,
            0xD8,
            0xFF,
            0xE0,
            0x00,
            0x10,
            0x4A,
            0x46,
            0x49,
            0x46,
            0x00,
            0x01,
            0x01,
            0x00,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,
            0xFF,
            0xDB,
            0x00,
            0x43,
            0x00,
            *([0x08] * 64),
            0xFF,
            0xC0,
            0x00,
            0x0B,
            0x08,
            0x00,
            0x01,
            0x00,
            0x01,
            0x01,
            0x01,
            0x11,
            0x00,
            0xFF,
            0xC4,
            0x00,
            0x14,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x03,
            0xFF,
            0xDA,
            0x00,
            0x08,
            0x01,
            0x01,
            0x00,
            0x00,
            0x3F,
            0x00,
            0x7F,
            0xFF,
            0xD9,
        ]
    )
    up = c.post(
        f"/capture/{token}/upload",
        files={"file": ("flare.jpg", io.BytesIO(jpeg), "image/jpeg")},
    )
    print("upload", up.status_code, up.text[:300])
    up.raise_for_status()

    chart = c.get(f"/chart/{session['encounter_id']}").json()
    print(
        "chart photos",
        len(chart.get("photos") or []),
        "compositions",
        len(chart.get("compositions") or []),
        "mode",
        chart.get("mode"),
    )
    print("OK FlareCheck smoke passed")


if __name__ == "__main__":
    main()
