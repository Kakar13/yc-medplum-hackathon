# YC x Medplum Hackathon

Medplum (S22) is hosting the **Agentic Healthcare Hackathon** at Y Combinator in San Francisco on **Aug 1, 2026**.

Blog: [YC x Medplum Hackathon](https://www.medplum.com/blog/yc-medplum-hackathon-2026)  
Sign up: https://events.ycombinator.com/medplum-hackathon-26  
Submit: [Hack submission form](https://docs.google.com/forms/d/e/1FAIpQLSdqhh466ADsUm-44CSkjC0xkOcm431wkJx_n_r7W4qT8FCRgA/viewform?usp=header)

## About (hackathon theme)

Imagine the doctor's office visit of the future. Prior to your visit, you check in by talking to a voice agent and your conversation is charted for you as it happens, translating into clinical documentation for the experts. Any health issue you describe is deep researched, even if it's just a simple rash and the voice agent tailors the conversation with full context of your history. You receive n=1 treatment that's customized just for you. Your treatment plan is peer reviewed by experts, and your data is visualized to enhance your understanding of the issues at hand. All this happens before you even see a doctor. And of course, you can ask how much treatment will cost ahead of time, and whether your insurance will cover it. That future is voice-first and buildable today, and this is the day to try it.

## What we're building

# Preflight — the pre-visit clinic

You check in by talking. The conversation charts itself into Medplum as it happens. Whatever
you describe — a knee, a cough, a rash, a worry — gets researched against real literature,
grounded in your own history, and turned into an n=1 plan that a clinician reviews before you
walk in. With the cost and coverage answered up front.

**And the part nobody has built:** every action that agent takes is bound to one patient by
its authorization, attributed in the record, and committed by a human.

That last part is why only ~3% of health systems have agentic AI in live workflows while 43%
are piloting it ([NEJM AI](https://ai.nejm.org/doi/full/10.1056/AI-S2501336), Jan 2026). It is
also measurable: [HAARF](https://github.com/Task-force-for-AI-agents-in-Healthcare/haarf), the
279-requirement regulatory framework from a 40+ expert task force, drives unauthorized tool
execution to 0% — but its wrong-patient scenario still passes only **6%** of the time with all
five of its middleware layers on, versus 16% with them off. None of those layers binds the
subject of care, so an agent authenticates perfectly and then names its patient in a free-text
tool argument.

Preflight's thesis: **the subject of care is a property of the agent's authorization, never an
argument the model chooses.** We replay HAARF's RT-1…RT-6 against our gateway and get 5/5
correct with 0 false positives, including the wrong-patient case they measured as unsolved —
plus 8/8 on Medplum-MCP-shaped `fhir-request` calls, where the patient hides inside a URL the
model composes.

This is the pattern [Medplum's own AI docs](https://www.medplum.com/docs/ai) describe — *"can
suggest, but not act"*, agents under the same policy framework as humans, an `AuditEvent` for
every AI action. Preflight implements that sentence and adds the missing piece: a way to
**verify** it is holding.

→ **[docs/AGENT_GOVERNANCE.md](docs/AGENT_GOVERNANCE.md)** — the thesis, the HAARF analysis, results, and honest limits

## How it maps to the brief

| The future described above | How Preflight does it |
|---|---|
| Check in by talking to a voice agent | Deepgram Nova-3 STT → LangGraph agent (`/voice/turn`) |
| Conversation charted as it happens | `chart_to_medplum` → Encounter + Observation + Composition |
| Any health issue deep researched | `deep_research` → Europe PMC, real citations only, never generated |
| Tailored with full context of your history | Moss hybrid retrieval over the patient's own record |
| n=1 treatment customized for you | `propose_care_plan` → CarePlan with per-patient reasoning + evidence |
| Peer reviewed by experts | `status: draft` + Task + Provenance; a human commits it at `/review` |
| Data visualized to enhance understanding | Clinician chart: note, photo, wearable Observations, citations |
| How much will it cost, will insurance cover it | `check_eligibility` → live Stedi test mode: real 271 parsed to *"$15 copay for an office visit, $0 deductible remaining"* |
| *(unstated but load-bearing)* | Patient-scoped capability gateway + AuditEvent on every decision |

## Stack

| Piece | Path |
|-------|------|
| Agent API (LangGraph, capability gateway, Medplum, Moss, Stedi, research) | [agent/README.md](agent/README.md) |
| Product UI (intake · `/capture` · chart · `/review` · `/trust`) | [web/README.md](web/README.md) |
| Governance thesis + HAARF scorecard | [docs/AGENT_GOVERNANCE.md](docs/AGENT_GOVERNANCE.md) |
| Product brief (science, market, psychology) | [docs/PRODUCT_BRIEF.md](docs/PRODUCT_BRIEF.md) |
| Closed-loop wearable synthesis | [docs/CLOSED_LOOP_SYNTHESIS.md](docs/CLOSED_LOOP_SYNTHESIS.md) |

```bash
# Terminal 1
cd agent && source .venv/bin/activate && uvicorn src.api:app --reload --port 8080
# Terminal 2
cd web && npm run dev

# The proof
cd agent && python scripts/haarf_scorecard.py
```

Then open http://localhost:5173 — intake at `/`, review queue at `/review`, governance at
`/trust`.

## Schedule | Aug 1, 2026 (PT)

| Time | Activity |
|------|----------|
| 9:00am | Doors open and breakfast |
| 10:00am | Opening remarks & sponsor intros |
| 12:30pm | Lunch |
| 3:00pm | Sponsor workshops / office hours |
| 5:00pm | Submissions close |
| 6:00pm | Dinner and presentations |
| 7:00pm | Awards |

## Prizes

- **First place:** YC interview + sponsor credits
- **Second place:** AirPods Max + sponsor credits
- **Third place:** Sponsor credits
- **People's Choice:** AirPods + sponsor credits — YouTube demo with the most views (counted at 5:00pm when submissions close)

Every attendee walks out with swag.

## Judging criteria

1. **Potential impact** — meaningfully improve patient care, clinician experience, or quality of care. Spirit of Agentic Healthcare: intelligent, standards-compliant, automated, voice-enabled; enhance clinicians rather than add workload.
2. **Effective use of provided technologies** — Deepgram, Medplum, moss.dev, and/or Stedi.

All four are live, not stubbed — `GET /health` reports each one:

| Sponsor | How it's used | Live? |
| --- | --- | --- |
| Medplum | FHIR CDR: Patient, Encounter, Observation, Composition, Binary, DocumentReference, CarePlan, Provenance, Task, AuditEvent. SMART scope `patient=<id>` is what makes the gateway enforceable server-side | yes (mock fallback when unconfigured) |
| Deepgram | Nova-3 STT for voice intake (`/voice/transcribe`, `/voice/turn`) | yes |
| moss.dev | Hybrid retrieval over the patient's own record, so the agent has history mid-conversation | yes |
| Stedi | Real-time eligibility (X12 270/271) in test mode; we parse the 271 into the numbers a patient asked for rather than echoing the payload | yes |

## Resources

- [Medplum docs](https://www.medplum.com/docs)
- [Building on Medplum with AI coding assistants](https://www.medplum.com/docs)
- [Stedi test mode](https://www.stedi.com)
- [Open Wearables](https://openwearables.io/docs) — unified Whoop / Oura / Fitbit / Garmin / Apple Health API ([GitHub](https://github.com/the-momentum/open-wearables))
- [Synthea](https://mitre.github.io/fhir-for-research/modules/synthea-overview) — synthetic FHIR sample patients
- Deepgram — free account with $200 credits (STT / TTS / voice agents); [Startup Program](https://deepgram.com) for credits after the event
- Medplum Discord → hackathon channel

## Agent skills

Cursor project skills (auto-discoverable):

| Skill | Path |
|-------|------|
| Hackathon context & judging | [`.cursor/skills/yc-medplum-hackathon/SKILL.md`](.cursor/skills/yc-medplum-hackathon/SKILL.md) |
| Medplum (FHIR / headless EHR) | [`.cursor/skills/medplum/SKILL.md`](.cursor/skills/medplum/SKILL.md) |
| Deepgram STT / TTS / Voice Agent | [`.cursor/skills/deepgram/SKILL.md`](.cursor/skills/deepgram/SKILL.md) |
| Stedi test mode (eligibility / claims) | [`.cursor/skills/stedi-healthcare/SKILL.md`](.cursor/skills/stedi-healthcare/SKILL.md) |
| Moss real-time retrieval | [`.cursor/skills/moss-dev/SKILL.md`](.cursor/skills/moss-dev/SKILL.md) |
| Open Wearables (Whoop/Oura/Fitbit/…) | [`.cursor/skills/open-wearables/SKILL.md`](.cursor/skills/open-wearables/SKILL.md) |
