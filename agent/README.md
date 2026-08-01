# FlareCheck agent — Medplum + Moss + LangGraph + Deepgram + Stedi

Between-visit **flare check-in**: eczema/rash photo via secure link + voice/text intake → FHIR chart → coverage → human handoff. Wearable risk (Open Wearables) remains available in the same loop.

## Architecture

```
Patient (phone / voice)
       ↓
Deepgram or text turn
       ↓
LangGraph agent
   ├── moss_search
   ├── ensure_patient / chart_to_medplum
   ├── send_photo_capture_link   ← 15m HMAC URL → web /capture/:token
   ├── get_wearable_risk         ← Open Wearables (optional)
   ├── check_eligibility         ← Stedi
   └── request_human_handoff
       ↓
Medplum: Encounter + Observation + Composition
         Binary (securityContext=Patient) + DocumentReference / Media
```

Secure photo path uses Medplum core ([Binary](https://www.medplum.com/docs/fhir-datastore/binary-data), [securityContext](https://www.medplum.com/docs/access/binary-security-context)). The phone never receives client secrets — only a FlareCheck token; upload is proxied by this API.

## Setup

```bash
cd agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill OPENAI, MEDPLUM_*, MOSS_*, DEEPGRAM_*, optional STEDI_*
# PUBLIC_APP_URL=http://localhost:5173
# PUBLIC_API_URL=http://localhost:8080
# AGENT_MODE=live   # when Medplum/Moss keys ready
```

## Run

```bash
# API (port 8080)
uvicorn src.api:app --reload --port 8080

# Web UI (separate terminal)
cd ../web && npm install && npm run dev

# CLI
python -m src.cli doctor
python -m src.cli once "My eczema on my elbows is flaring and I can't sleep"

# Eczema fixtures → Moss long-term index (usemoss/moss: upsert + load_index)
python -m src.synthea_import --bundle data/synthea/sample_eczema_bundle.json
python -m src.seed_moss
# Live calls also use Moss sessions per encounter — see src/moss_retriever.py
# https://github.com/usemoss/moss

# E2E smoke (API must be up)
python scripts/smoke_flarecheck.py
```

### Key HTTP routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Integration flags |
| POST | `/session/start` | Patient + Encounter |
| POST | `/turn` | Agent turn |
| POST | `/capture-links` | Issue secure photo URL |
| GET | `/capture/{token}` | Capture page metadata |
| POST | `/capture/{token}/upload` | Photo → Medplum Binary + DocumentReference |
| GET | `/chart/{encounterId}` | Clinician BFF |
| GET | `/binary/{binaryId}` | Stream photo bytes to the chart (creds stay server-side) |
| GET | `/wearables/whoop/status` | Whoop app configured / strap connected |
| GET | `/wearables/whoop/authorize` | Start Whoop OAuth (returns URL to open) |
| GET | `/wearables/whoop/callback` | Whoop redirect → token exchange → back to app |
| GET | `/wearables/whoop/summaries` | Latest recovery + sleep (normalized and raw) |
| GET | `/wearables/risk` | Triage level from the connected strap, else mock |
| POST | `/wearables/to-chart` | Wearable snapshot → coded FHIR Observations |

## Connect a real Whoop

1. Sign in at [developer-dashboard.whoop.com](https://developer-dashboard.whoop.com/) with your Whoop account (needs an active membership), create a Team, then an App.
2. Scopes: `offline read:recovery read:sleep read:cycles read:workout read:body_measurement read:profile`.
3. Redirect URI must be exactly `http://localhost:8080/wearables/whoop/callback`.
4. Put `WHOOP_CLIENT_ID` / `WHOOP_CLIENT_SECRET` in `.env` and restart the API.
5. Click **Connect my Whoop** on the web app, authorize, and you land back with `?whoop=connected`.
6. **Pull signals into chart** writes resting HR, HRV, SpO2, skin temp, recovery, sleep duration/efficiency/awake time as coded `Observation`s on the encounter.

Tokens are stored in `agent/.whoop_tokens.json` (gitignored, `0600`) and auto-refreshed via the `offline` scope. Without credentials the same routes return mock summaries, so the demo never hard-fails.

Closed-loop framing and the eczema signal rationale: [`docs/CLOSED_LOOP_SYNTHESIS.md`](../docs/CLOSED_LOOP_SYNTHESIS.md).

## Progress

- [x] LangGraph + Moss + Medplum + Stedi + handoff
- [x] Open Wearables risk tool
- [x] Whoop API v2 OAuth + eczema-aware risk rules + FHIR Observation write-through
- [x] Photo preview streamed to clinician chart via `/binary/{id}`
- [x] Synthea eczema bundle + importer
- [x] Secure capture tokens + Medplum Binary/DocumentReference path
- [x] FastAPI BFF + web capture/chart UI
- [x] Browser mic → Deepgram Nova-3 → `/voice/turn` → LangGraph (key server-side)
- [ ] Live Medplum ClientApplication credentials (fill `.env`)
- [ ] Full Deepgram Voice Agent WebSocket (duplex TTS) — mic STT path works now

### Loop (build → smoke)

```bash
# One tick
bash scripts/loop_tick.sh

# Agent keeps a fixed 10m loop armed in Cursor that runs smoke then wakes to ship the next gap.
```
