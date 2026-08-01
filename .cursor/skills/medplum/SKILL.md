---
name: medplum
description: >-
  Build on Medplum, the open-source headless EHR and FHIR developer platform.
  Use when creating Patients/Encounters/chart data, using MedplumClient, Bots,
  React components, $ai, Stedi eligibility/claims, Auth, or when the user
  mentions Medplum, FHIR CDR, or app.medplum.com.
---

# Medplum

Docs: [medplum.com/docs](https://www.medplum.com/docs) · Repo: [github.com/medplum/medplum](https://github.com/medplum/medplum) · App: [app.medplum.com](https://app.medplum.com)

Medplum is a **headless EHR** / healthcare developer platform: Auth (OAuth/OIDC/SMART), FHIR Clinical Data Repository, FHIR API, TypeScript SDK, App, Bots, and React UI components.

## Agent instructions

1. **Store clinical data as FHIR** — never invent ad-hoc schemas for patients, visits, notes, coverage, or plans.
2. Prefer `@medplum/core` `MedplumClient` + `@medplum/fhirtypes` over raw `fetch` unless necessary.
3. Scope resources with correct `subject` / `patient` / `encounter` references (`createReference`).
4. For voice/agent hacks: Deepgram/Moss produce unstructured text → **structure into FHIR** (Encounter, Observation, Condition, Composition/DocumentReference, Coverage, CarePlan).
5. AI agents are subject to the same AccessPolicies as humans; do not bypass auth. Prefer “suggest then human confirm” for clinical writes when demoing safety.
6. Use hosted Medplum for the hackathon unless self-hosting is required; register at [app.medplum.com/register](https://app.medplum.com/register).

## Quick start

1. Register a project: https://app.medplum.com/register
2. Optional: import sample data; explore [Provider app](https://www.medplum.com/docs)
3. Create a **ClientApplication** (Project Admin) for machine access — note `ID` + `Secret`
4. Build against `https://api.medplum.com/`

```bash
npm install @medplum/core @medplum/fhirtypes
# UI apps:
npm install @medplum/react @medplum/react-hooks
```

```ts
import { MedplumClient, createReference } from '@medplum/core';
import type { Patient, Encounter, Composition } from '@medplum/fhirtypes';

const medplum = new MedplumClient({ baseUrl: 'https://api.medplum.com/' });
await medplum.startClientLogin(process.env.MEDPLUM_CLIENT_ID!, process.env.MEDPLUM_CLIENT_SECRET!);

const patient = await medplum.createResource<Patient>({
  resourceType: 'Patient',
  name: [{ family: 'Smith', given: ['Jordan'] }],
});

const encounter = await medplum.createResource<Encounter>({
  resourceType: 'Encounter',
  status: 'in-progress',
  class: { system: 'http://terminology.hl7.org/CodeSystem/v3-ActCode', code: 'VR' }, // virtual as needed
  subject: createReference(patient),
});
```

Client credentials: [Auth docs](https://www.medplum.com/docs/auth/client-credentials) · `POST /oauth2/token` or `startClientLogin`.

## Local clone (hackathon workspace)

Shallow clone lives at `infra/medplum/` (gitignored, ~317MB). Do **not** commit it.

```bash
# if missing:
git clone --depth 1 https://github.com/medplum/medplum.git infra/medplum
```

For FlareCheck today: prefer **hosted** `api.medplum.com` + ClientApplication. Full local stack needs Postgres+Redis (`docker-compose.yml`), Node 22/24, `npm ci` + build — heavy for demo day.

## Product surface (monorepo categories)

From [medplum/medplum](https://github.com/medplum/medplum) `packages/` + `examples/`:

### Platform core (what FlareCheck already uses via API)
| Package | Role |
|---------|------|
| `server` | FHIR CDR + Auth + bots runtime |
| `app` | Hosted admin/provider UI at app.medplum.com |
| `core` | `@medplum/core` — `MedplumClient`, helpers |
| `fhirtypes` | TypeScript FHIR types |
| `fhir-router` | FHIR URL routing |
| `mock` | Mock client for tests |
| `cli` / `create-medplum` | Project scaffolding & deploy |
| `definitions` | Terminology / data defs |
| `docs` | Docs source (Markdown) |

### App building
| Package | Role |
|---------|------|
| `react` / `react-hooks` | Chart UI components + hooks |
| `storybook` | Component gallery |
| `graphiql` | GraphQL explorer |
| `bot-layer` | AWS Lambda layer for Bots |

### Interop / clinical network
| Package | Role |
|---------|------|
| `hl7` | HL7v2 client/server |
| `ccda` | C-CDA |
| `agent` | On-prem agent (site connectivity) |
| `health-gorilla-*` | Lab ordering (Health Gorilla) |
| `dosespot-*` / `scriptsure-react` | eRx |
| `cdk` | AWS self-host infra |

### Example apps most relevant to FlareCheck
| Example | Why it matters |
|---------|----------------|
| `medplum-provider` | Charting, visits, tasks, GraphQL chart |
| `medplum-eligibility-demo` | Coverage + eligibility request/response (+ bot) |
| `medplum-patient-intake-demo` | Intake → Questionnaire/Patient |
| `medplum-hello-world` | Minimal Vite + MedplumClient |
| `medplum-demo-bots` | Bot patterns |
| `medplum-task-demo` | Human handoff Tasks |
| `medplum-websocket-subscriptions-demo` | Live chart updates |
| `foomedical` | Full patient-facing reference |

Also: SMART-on-FHIR, Photon pharmacy, eFax, FHIRcast, multilingual, MSO, FSH profiles, Postman, local k8s.

Stack: TypeScript, PostgreSQL, Redis, Express, React. Local setup: [local-dev-setup](https://www.medplum.com/docs/contributing/local-dev-setup).

## FHIR patterns for this hackathon

| Flow | Resources |
|------|-----------|
| Voice intake / pre-visit | `Patient`, `Encounter`, `Observation`, `Condition`, `AllergyIntolerance`, `Composition` or `DocumentReference` (note) |
| Chart / history | Chart data model — see [Charting](https://www.medplum.com/docs/charting) |
| Coverage / cost | `Coverage`, `CoverageEligibilityRequest` / `CoverageEligibilityResponse` (+ Stedi) |
| Care plan / orders | `CarePlan`, `ServiceRequest`, `MedicationRequest`, `Task` (peer review) |
| Intake forms | `Questionnaire` → `QuestionnaireResponse` → Bot extracts Patient / ServiceRequest |

Charting overview: [Charting](https://www.medplum.com/docs/charting) · sample UI: [medplum-provider](https://github.com/medplum/medplum) examples / Provider app.

Search example:

```ts
const patients = await medplum.searchResources('Patient', 'name=Smith');
const encounters = await medplum.searchResources('Encounter', `subject=Patient/${patient.id}`);
```

## Bots (serverless clinical logic)

Bots run on resource create/update (or HTTP invoke). Single TS file exporting `handler`:

```ts
import { BotEvent, MedplumClient } from '@medplum/core';
import type { Patient } from '@medplum/fhirtypes';

export async function handler(medplum: MedplumClient, event: BotEvent): Promise<any> {
  const patient = event.input as Patient;
  console.log(patient.name?.[0]?.family);
  return true;
}
```

Docs: [Bot Basics](https://www.medplum.com/docs/bots/bot-basics) · production CLI deploy: [Bots in Production](https://www.medplum.com/docs/bots/bots-in-production).

Use bots to: turn QuestionnaireResponse → Patient/ServiceRequest; post-process voice chart drafts; fan out Tasks for peer review.

## AI on Medplum

Philosophy: AI needs FHIR APIs, permissions, and audit — see [Build with AI](https://www.medplum.com/docs/ai).

### `$ai` operation

`POST [base]/fhir/R4/$ai` — OpenAI (or LiteLLM via `LLM_BASE_URL` secret). Requires project feature `ai` + secret `OPENAI_API_KEY`.

```ts
const response = await medplum.fhirUrl('$ai').post({
  resourceType: 'Parameters',
  parameter: [
    { name: 'messages', valueString: JSON.stringify([{ role: 'user', content: 'Summarize this intake…' }]) },
    { name: 'model', valueString: 'gpt-4o-mini' },
  ],
});
```

Supports `tools` / `fhir_request` suggestions — **your app executes** FHIR ops after validating permissions. Streaming: `Accept: text/event-stream` (no tool calls in stream mode).

Full guide: [$ai Operation](https://www.medplum.com/docs/ai/ai-operation) · Provider **Spaces** in-app assistant: [Spaces](https://www.medplum.com/docs/provider/spaces) · MCP: Medplum AI MCP (see AI docs).

## Stedi (billing / eligibility)

Native integration: [Stedi Integration](https://www.medplum.com/docs/integration/stedi)

- Eligibility: `CoverageEligibilityRequest` → `CoverageEligibilityResponse` (270/271)
- Claims: `Claim` + `$stedi-submit-claim`
- Responses: 277CA / 835 via webhooks → `DocumentReference`

For the hackathon, prefer **Stedi test mode** (see [stedi-healthcare](../stedi-healthcare/SKILL.md)); map mock benefits into Medplum Coverage / eligibility resources for the demo UI.

## Auth & projects

- Projects isolate FHIR data, users, bots, clients ([register](https://www.medplum.com/docs/tutorials/register))
- Profiles: `Practitioner`, `Patient`, `RelatedPerson`
- AccessPolicies govern what AI and humans can read/write; actions produce `AuditEvent`

## Hackathon wiring

```
Deepgram (voice) → transcript / ConversationText
       ↓
Moss (optional) → grounded context from history/FAQ
       ↓
Structure with LLM ($ai or your model) → FHIR create/update via MedplumClient
       ↓
Stedi test eligibility → show cost/coverage on CoverageEligibilityResponse
       ↓
UI: @medplum/react or custom viz on Patient chart
```

Demo tip: one Patient + one in-progress Encounter + live Composition update as the voice agent talks is enough to show “charted as it happens.”

## Help

- Discord: https://discord.gg/medplum (hackathon channel during the event)
- Docs search / AI coding assistants section on [docs home](https://www.medplum.com/docs)
- YouTube + Storybook linked from docs community footer
