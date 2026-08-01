---
name: open-wearables
description: >-
  Connect Whoop, Oura, Fitbit, Garmin, Apple Health and other wearables via the
  Open Wearables unified API. Use when building wearable OAuth, recovery/sleep/
  HRV risk signals, Open Wearables self-host, or when the user mentions Whoop,
  Oura, Fitbit, Garmin, or openwearables.io.
---

# Open Wearables

Unified open-source API for wearable health data. Self-hosted (MIT), one REST surface for many providers instead of per-vendor SDKs.

- Docs: [openwearables.io/docs](https://openwearables.io/docs)
- API ref: [API introduction](https://openwearables.io/docs/api-reference/introduction)
- GitHub: [the-momentum/open-wearables](https://github.com/the-momentum/open-wearables)
- Integration guide: [dev-guides/integration-guide](https://openwearables.io/docs/dev-guides/integration-guide)

## Agent instructions

1. **Prefer Open Wearables** over direct Whoop/Oura/Fitbit SDKs for this hackathon — one OAuth + one schema.
2. Auth header is **`X-Open-Wearables-API-Key`** (not Bearer).
3. Provider path names are **lowercase**: `whoop`, `oura`, `fitbit`, `garmin`, `polar`, `suunto`, `strava`, `apple`.
4. Risk language only: recovery/HRV/sleep **deviation → outreach**, never “predictive diagnosis.”
5. For demos without a live stack, use `AGENT_MODE=mock` wearable fixtures in `agent/src/open_wearables.py`.
6. You still need **per-provider developer credentials** in the Open Wearables `.env` (Whoop/Oura/Fitbit portals) — Open Wearables does not replace vendor app registration.

## Supported providers (high level)

| Provider | Style | Notes |
|----------|--------|--------|
| Whoop | Cloud OAuth + webhooks | Recovery, sleep, HRV, SpO2, workouts |
| Oura | Cloud OAuth | Sleep, readiness, HRV, temp |
| Fitbit | Cloud OAuth (poll) | Activity primary today; HR/sleep expanding |
| Garmin / Polar / Suunto / Strava | Cloud OAuth | Often need vendor partner approval |
| Apple Health / Health Connect | Mobile SDK | HealthKit / Android — not pure REST |

Full list: [supported providers](https://openwearables.io/docs/providers/supported)

## Auth & base URL

```http
X-Open-Wearables-API-Key: YOUR_API_KEY
```

Local default: `http://localhost:8000/api/v1`  
Swagger: `http://localhost:8000/docs` or `https://api.openwearables.io/docs`

## Connect flow (all providers)

1. `POST /api/v1/users` — `{ "email", "external_user_id" }`
2. `GET /api/v1/oauth/{provider}/authorize?user_id={id}&redirect_uri=...`
3. Redirect user to `authorization_url`
4. Open Wearables handles callback + token storage + initial sync
5. Read normalized data from summaries / events / timeseries

```bash
# Authorize Whoop (same pattern for oura, fitbit, ...)
curl -X GET "$OW_BASE/oauth/whoop/authorize?user_id=$USER_ID&redirect_uri=http://localhost:3000/connected" \
  -H "X-Open-Wearables-API-Key: $OW_API_KEY"
```

## Data endpoints we care about (risk → voice)

| Need | Endpoint |
|------|----------|
| Recovery / HRV / RHR | `GET /users/{id}/summaries/recovery` |
| Sleep | `GET /users/{id}/summaries/sleep` |
| Activity | `GET /users/{id}/summaries/activity` |
| Body | `GET /users/{id}/summaries/body` |
| Scores | `GET /users/{id}/health-scores` |
| Workouts / sleep events | `GET /users/{id}/events/workouts` · `/events/sleep` |
| Timeseries HR | `GET /users/{id}/timeseries?types=heart_rate&...` |
| Manual sync | `POST /providers/{provider}/users/{id}/sync` |

## Hackathon wiring (this repo)

- Client: `agent/src/open_wearables.py`
- Tool: `get_wearable_risk` → feeds `wearable_context` into LangGraph / voice
- Env: `OPEN_WEARABLES_BASE_URL`, `OPEN_WEARABLES_API_KEY`, `OPEN_WEARABLES_USER_ID`

Pitch fit: **free data off the phone** (or wrist) → normalized risk signal → Deepgram check-in → Moss history → Medplum chart → Stedi → human handoff.

## Do not

- Claim diagnosis from recovery scores
- Commit vendor client secrets or Open Wearables API keys
- Build four separate OAuth stacks when Open Wearables already unifies them
