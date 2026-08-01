# Clinical voice agent — Medplum + Moss + LangGraph + Deepgram + Stedi + Open Wearables

Foundation stack while product direction is still open. Direction-agnostic: works for wearable-triggered outreach **or** plain pre-visit intake.

## Architecture

```
Whoop / Oura / Fitbit / Garmin / Apple Health …
       ↓
Open Wearables (unified OAuth + recovery/sleep/HRV)
       ↓
Risk signal → Deepgram voice check-in (STT / Voice Agent + function calling)
       ↓
LangGraph ReAct agent            ← tools + memory (thread_id)
   ├── get_wearable_risk         ← Open Wearables summaries
   ├── moss_search               ← Moss / Synthea fixtures
   ├── ensure_patient            ← Medplum Patient
   ├── chart_to_medplum          ← Encounter + Observation + Composition
   ├── check_eligibility         ← Stedi test / mock
   └── request_human_handoff     ← co-regulation / algorithm aversion
       ↓
Medplum FHIR CDR
```

Docs used:

- [Open Wearables](https://openwearables.io/docs) — Whoop, Oura, Fitbit, Garmin, Apple Health, …
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) + [voice agents](https://docs.langchain.com/oss/python/langchain/voice-agent)
- [Moss × LangChain](https://docs.moss.dev/docs/integrations/langchain)
- [Medplum](https://www.medplum.com/docs) via [pymedplum](https://pypi.org/project/pymedplum/)
- [Deepgram Voice Agent](https://developers.deepgram.com/docs/build-a-voice-agent) + [function calling](https://developers.deepgram.com/docs/voice-agents-function-calling)
- [Stedi test mode / eligibility](https://www.stedi.com/docs/healthcare/test-mode)
- [Synthea](https://mitre.github.io/fhir-for-research/modules/synthea-overview) — synthetic FHIR patients

## Setup

```bash
cd agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill keys when ready; AGENT_MODE=mock works offline (OpenAI optional)
```

### Keys

| Var | Where |
|-----|--------|
| `OPENAI_API_KEY` | OpenAI (LangGraph think) |
| `MEDPLUM_CLIENT_ID` / `SECRET` | [app.medplum.com](https://app.medplum.com) → Client Application |
| `MOSS_PROJECT_ID` / `KEY` | [moss.dev](https://www.moss.dev) portal |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) |
| `STEDI_API_KEY` | Stedi portal → **Test** API key |
| `OPEN_WEARABLES_*` | Self-host [Open Wearables](https://github.com/the-momentum/open-wearables); API key from dashboard |

`AGENT_MODE=mock` uses local `data/sample_history.json` + in-memory FHIR + mock eligibility + mock wearable risk.  
`AGENT_MODE=live` hits real Medplum + Moss (+ OpenAI / Stedi / Open Wearables when keyed).

### Open Wearables (Whoop / Oura / Fitbit / …)

One API instead of four OAuth stacks. Auth header: `X-Open-Wearables-API-Key`.

```bash
# Risk snapshot (mock elevated RHR / low recovery by default)
curl http://localhost:8080/wearables/risk

# OAuth authorize URL for a provider (whoop|oura|fitbit|garmin|…)
curl "http://localhost:8080/wearables/oauth/whoop/authorize?user_id=USER&redirect_uri=http://localhost:3000/connected"
```

You still register apps in each vendor portal (Whoop / Oura / Fitbit / …) and put those client IDs into the **Open Wearables** server `.env` — our agent only talks to Open Wearables.

## Run

```bash
# Integration smoke check
python -m src.cli doctor

# Seed Moss index (live) or list fixtures (mock)
python -m src.seed_moss

# One turn
python -m src.cli once "I've been wheezing since last night and used my inhaler four times."

# Interactive text "voice" session
python -m src.cli chat

# HTTP API
uvicorn src.api:app --reload --port 8080
# GET  http://localhost:8080/health
# GET  http://localhost:8080/wearables/risk
# POST http://localhost:8080/turn  {"message":"...","wearable_context":"..."}
# POST http://localhost:8080/deepgram/function  — FunctionCallRequest stub → LangGraph
```

In chat: type as the patient; `/handoff` forces human escalation; ask about **insurance/cost** for Stedi mock; `/quit` exits.

## Synthetic FHIR (Synthea)

Hackathon tip: use [Synthea](https://mitre.github.io/fhir-for-research/modules/synthea-overview) for sample patients — open-source synthetic FHIR (not de-identified real data). Pre-generated sets: [synthea.mitre.org/downloads](https://synthea.mitre.org/downloads).

This repo ships a **Synthea-shaped** asthma Bundle at `data/synthea/sample_asthma_bundle.json`. Convert any Bundle → Moss docs:

```bash
# Rebuild data/sample_history.json from the sample Bundle
python -m src.synthea_import

# Or point at a real Synthea export (one patient Bundle JSON)
python -m src.synthea_import --bundle ~/Downloads/synthea/Aaron697_*.json --out data/sample_history.json

# Optionally create Patient in Medplum when live
python -m src.synthea_import --medplum
```

Then `python -m src.seed_moss` / `python -m src.cli once "..."`.

## Progress (loop)

- [x] LangGraph + Moss + Medplum tools (mock + live hooks)
- [x] Human handoff tool
- [x] Stedi `check_eligibility` (mock default; live test key optional)
- [x] FastAPI `/health`, `/turn`, `/deepgram/function`
- [x] Moss seed script
- [x] Deepgram Settings helper with `clinical_turn` function definition
- [ ] Full Deepgram Voice Agent WebSocket client (mic ↔ WS)
- [x] Synthea / Synthea-shaped FHIR Bundle → Moss docs importer
- [x] Open Wearables client + `get_wearable_risk` (Whoop/Oura/Fitbit/… mock + live)
- [ ] Seed Moss from live Medplum Patient graph
- [ ] Clinician UI for Composition

## Human handoff

Tool `request_human_handoff` implements: agents prepare the chart; humans soothe (co-regulation / algorithm aversion).
