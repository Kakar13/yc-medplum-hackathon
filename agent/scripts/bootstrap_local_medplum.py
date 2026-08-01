#!/usr/bin/env python3
"""Point Preflight at a self-hosted Medplum instead of the in-memory mock.

Creates a project on a locally running Medplum server, mints a ClientApplication for the agent,
and writes the credentials into `agent/.env`. Idempotent: re-running reuses the existing user and
creates a fresh client application.

Prerequisites — the local stack must be up:

    docker compose -f infra/medplum/docker-compose.full-stack.yml \
                   -f infra/medplum-local.override.yml up -d

The override blanks Medplum's bundled reCAPTCHA test keys; with them set the server rejects
`/auth/newuser` because a scripted caller cannot produce a recaptcha token.

The secret is written to `.env` and never printed, so it does not end up in terminal scrollback
or CI logs.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import sys
from pathlib import Path

import httpx

BASE = "http://localhost:8103"
APP_URL = "http://localhost:3000"
EMAIL = "demo@preflight.local"
PASSWORD = "PreflightDemo123!"
PROJECT = "Preflight"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def pkce() -> tuple[str, str]:
    """Medplum requires PKCE on the authorization_code exchange for password logins.

    Without a code challenge recorded at login the token endpoint refuses the code with
    'Missing verification context' — see packages/server/src/oauth/token.ts.
    """
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    return verifier, challenge


def write_env(updates: dict[str, str]) -> None:
    """Update keys in .env in place, preserving order, comments and unrelated entries."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = re.match(r"^([A-Z0-9_]+)=", line)
        key = match.group(1) if match else None
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=60)

    try:
        health = client.get("/healthcheck").json()
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Medplum at {BASE}: {exc}")
        print("Start it with: docker compose -f infra/medplum/docker-compose.full-stack.yml \\")
        print("               -f infra/medplum-local.override.yml up -d")
        return 1
    print(f"Medplum {health.get('version')} up (postgres={health.get('postgres')})")

    verifier, challenge = pkce()

    # First run creates the project; later runs just log in.
    resp = client.post(
        "/auth/newuser",
        json={
            "firstName": "Preflight",
            "lastName": "Demo",
            "email": EMAIL,
            "password": PASSWORD,
            "projectName": PROJECT,
            "codeChallenge": challenge,
            "codeChallengeMethod": "S256",
        },
    )
    if resp.status_code < 400:
        login_id = resp.json()["login"]
        resp = client.post(
            "/auth/newproject", json={"login": login_id, "projectName": PROJECT}
        )
        if resp.status_code >= 400:
            print(f"newproject failed: {resp.status_code} {resp.text[:200]}")
            return 1
        code = resp.json().get("code")
        print(f"created project {PROJECT!r}")
    else:
        resp = client.post(
            "/auth/login",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "scope": "openid",
                "codeChallenge": challenge,
                "codeChallengeMethod": "S256",
            },
        )
        if resp.status_code >= 400:
            print(f"login failed: {resp.status_code} {resp.text[:200]}")
            return 1
        body = resp.json()
        code = body.get("code")
        if not code:
            membership = (body.get("memberships") or [])[0]["id"]
            resp = client.post(
                "/auth/profile", json={"login": body["login"], "profile": membership}
            )
            code = resp.json().get("code")
        print("reusing existing project")

    resp = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": APP_URL,
        },
    )
    if resp.status_code >= 400:
        print(f"token exchange failed: {resp.status_code} {resp.text[:200]}")
        return 1
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    me = client.get("/auth/me", headers=headers).json()
    project = me.get("project") or {}
    print(f"project id {project.get('id')}")

    # Must go through the admin route, not a plain FHIR create: only this path runs
    # generateSecret() server-side (packages/server/src/admin/client.ts). A FHIR POST yields a
    # ClientApplication with no secret, which cannot authenticate.
    resp = client.post(
        f"/admin/projects/{project.get('id')}/client",
        headers=headers,
        json={
            "name": "Preflight Agent",
            "description": "Pre-visit voice intake agent",
        },
    )
    if resp.status_code >= 400:
        print(f"could not create ClientApplication: {resp.status_code} {resp.text[:200]}")
        return 1
    app = resp.json()
    if not app.get("secret"):
        print(f"ClientApplication {app.get('id')} came back without a secret; cannot continue")
        return 1

    write_env(
        {
            "AGENT_MODE": "live",
            "MEDPLUM_BASE_URL": f"{BASE}/",
            "MEDPLUM_CLIENT_ID": app["id"],
            "MEDPLUM_CLIENT_SECRET": app["secret"],
        }
    )
    print(f"client application {app['id']}")
    print(f"credentials written to {ENV_PATH}")
    print(f"\nMedplum UI: {APP_URL}  ({EMAIL} / {PASSWORD})")
    print("Restart the agent API to pick up the new environment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
