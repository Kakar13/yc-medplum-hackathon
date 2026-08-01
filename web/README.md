# FlareCheck web

Thin product UI for the YC × Medplum hackathon agent.

| Route | Job |
|-------|-----|
| `/` | Start flare check-in, show agent reply + secure capture link |
| `/capture/:token` | Mobile photo upload (Medplum via API proxy) |
| `/chart/:encounterId` | Clinician chart (Composition, observations, photo, Stedi) |

No Medplum secrets in the browser — all FHIR writes go through `http://localhost:8080`.

```bash
cp .env.example .env
npm install
npm run dev
# http://localhost:5173
```

Run the agent API first: `cd ../agent && uvicorn src.api:app --reload --port 8080`.
