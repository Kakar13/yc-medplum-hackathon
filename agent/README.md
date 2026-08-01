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

# Eczema fixtures → Moss docs
python -m src.synthea_import --bundle data/synthea/sample_eczema_bundle.json
python -m src.seed_moss

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

## Progress

- [x] LangGraph + Moss + Medplum + Stedi + handoff
- [x] Open Wearables risk tool
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
