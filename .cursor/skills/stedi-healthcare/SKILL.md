---
name: stedi-healthcare
description: >-
  Build and test Stedi healthcare eligibility and claims flows in test mode
  without PHI/PII. Use when implementing insurance eligibility checks, mock
  270/271 benefits, test claims, Stedi MCP/Agent, cost/coverage demos, or when
  the user mentions Stedi, eligibility, payers, deductibles, or copays.
---

# Stedi Healthcare (Test Mode)

Source: [Stedi Test Mode](https://www.stedi.com/docs/healthcare/test-mode)

Test mode is a separate environment to simulate Stedi transactions **without PHI/PII** and **without sending data to payers**. Sandbox accounts are test-only. Production accounts toggle **Test mode ON** via account name in the side nav.

Mock transactions in test mode are **free**.

## Agent instructions

1. Prefer **test API keys** and mock eligibility requests for all hackathon demos.
2. Never send real PHI/PII. Use Stedi's predefined mock subscriber values exactly.
3. Map Stedi benefits (active coverage, copay, deductible) into Medplum `Coverage` / display UX — do not invent payer responses.
4. For AI agents: use Stedi MCP with a **test** API key when available (production accounts only for MCP).
5. If eligibility fails with recoverable AAA errors, point users at Debug view / Stedi Agent.

## Generate test API keys

1. Log into [Stedi portal](https://portal.stedi.com/app)
2. Account name → **API Keys** → **Generate new API Key**
3. Name with `test` prefix; choose **Test** as key type
4. Copy the key; use for mock eligibility APIs only

Auth docs: [API authentication](https://www.stedi.com/docs/healthcare/api-reference#authentication)

## Mock eligibility checks

Submit via:

- UI: [eligibility check form](https://portal.stedi.com/app/healthcare/checks/create) (Test mode ON)
- API: [mock eligibility requests](https://www.stedi.com/docs/healthcare/api-reference/mock-requests-eligibility-checks)

Predefined payers include **Aetna**, **Cigna**, **UnitedHealthcare**, **CMS**, plus others (Anthem, Humana, Kaiser, dental payers, etc.). Responses include realistic copays, deductibles, patient responsibility, and active/inactive coverage.

Also available: mock **MBI lookup** (SSN → Medicare Beneficiary Identifier + benefits from CMS).

### Mock request rules (critical)

- Use a **test API key**. Production payloads with a test key error.
- **Subscriber fields must match mock fixtures exactly** (name, DOB, member ID, SSN). Other values return errors.
- Medical: service type code `30` typically; dental: `35`.
- Provider: any org name + NPI that passes check-digit validation (dummy NPI OK).

### Common AAA error mocks

Useful for demos/troubleshooting: `42`, `43`, `72`, `73`, `75`, `79` — see [mock requests](https://www.stedi.com/docs/healthcare/api-reference/mock-requests-eligibility-checks).

## Review results

[Eligibility searches](https://portal.stedi.com/app/healthcare/eligibility):

- History filterable by status, payer ID, date, error code
- Raw API request/response
- Benefits table (coverage + payment responsibilities)
- **Debug** view for systematic recovery to a successful response

## Stedi MCP server

Works with test mode for AI agents (no PHI/PII). **Production accounts only** — sandbox must upgrade.

Tools:

- Search payers (payer ID + supported transactions)
- Run eligibility checks (properly formatted requests)
- Troubleshoot errors (e.g. Subscriber Not Found)

Install: [Stedi MCP server](https://www.stedi.com/docs/healthcare/mcp-server). Connect with **test** API keys.

## Stedi Agent

Resolves recoverable eligibility errors with support-style best practices.

1. New eligibility check → payer **Stedi Agent** (defaults OK)
2. Submit — designed to fail with AAA `73` (Invalid/Missing Subscriber/Insured Name)
3. **Resolve with Stedi Agent** → Debug view → successful mock benefits
4. **View check** for full response

## Test claims

Production accounts only (sandbox must upgrade). View in [claims](https://portal.stedi.com/app/healthcare/claims) with Test mode ON. Portal UI claim submit not supported — use API/SFTP.

- JSON: `usageIndicator` = `T`
- X12 / SFTP: `ISA15` = `T`

See [test claims workflow](https://www.stedi.com/docs/healthcare/test-claims-workflow) for 277CA / 835 ERA from Stedi Test Payer.

## Not supported in test mode

- Transaction enrollment
- Insurance discovery checks
- Coordination of benefits (COB)
- Submitting claims via portal UI
- 275 claim attachments
- 276/277 real-time claim status
- Custom mock data or arbitrary payer selection

## Hackathon pattern

**Cost / coverage before the visit:** voice or UI asks "will insurance cover this?" → Stedi mock eligibility (test key) → show active coverage + copay/deductible → optionally persist summary on Medplum `Coverage` / related resources. Never call production payers during the hack.
