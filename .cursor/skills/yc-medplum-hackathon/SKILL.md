---
name: yc-medplum-hackathon
description: >-
  Context and build guidance for the YC x Medplum Agentic Healthcare Hackathon
  (Aug 1, 2026). Use when building hacks, choosing stack (Medplum, Deepgram,
  moss.dev, Stedi), aligning with judging criteria, preparing demos/submissions,
  or when the user mentions the Medplum hackathon, agentic healthcare, or
  voice-first clinical workflows.
---

# YC x Medplum Hackathon

Medplum (S22) is hosting the **Agentic Healthcare Hackathon** at Y Combinator in San Francisco on **Saturday, August 1, 2026**.

Source: [YC x Medplum Hackathon blog](https://www.medplum.com/blog/yc-medplum-hackathon-2026)

## Vision (build toward this)

Imagine the doctor's office visit of the future. Prior to your visit, you check in by talking to a voice agent and your conversation is charted for you as it happens, translating into clinical documentation for the experts. Any health issue you describe is deep researched, even if it's just a simple rash and the voice agent tailors the conversation with full context of your history. You receive n=1 treatment that's customized just for you. Your treatment plan is peer reviewed by experts, and your data is visualized to enhance your understanding of the issues at hand. All this happens before you even see a doctor. And of course, you can ask how much treatment will cost ahead of time, and whether your insurance will cover it. That future is voice-first and buildable today, and this is the day to try it.

## Agent instructions

When helping on this project:

1. **Optimize for judging** — see criteria below. Prefer demos that improve patient care or clinician experience without adding workload.
2. **Use sponsor tech** — Deepgram, Medplum, moss.dev, and/or Stedi should be first-class in the architecture, not bolted on.
3. **Stay FHIR / standards-aware** — Medplum is FHIR-native; prefer real FHIR resources over ad-hoc schemas when storing clinical data. For wearables, prefer [Open Wearables](https://openwearables.io/docs) (Whoop/Oura/Fitbit/…) over per-vendor OAuth — see skill `open-wearables`.
4. **Voice-first when it fits** — Deepgram for STT/TTS/voice agents; chart as the conversation happens.
5. **Demo by 5:00pm PT** — submissions close then; keep scope shippable. Prefer a crisp vertical slice over unfinished breadth.
6. **People's Choice** — post a YouTube demo video; views counted at 5:00pm when submissions close.

## Schedule | Aug 1, 2026 (PT)

| Time | Activity |
|------|----------|
| 9:00am | Doors open and breakfast |
| 10:00am | Opening remarks and sponsor intros |
| 12:30pm | Lunch |
| 3:00pm | Sponsor workshops and office hours |
| 5:00pm | Submissions close |
| 6:00pm | Dinner and presentations |
| 7:00pm | Awards |

## Prizes

- **First place:** YC interview + sponsor credits
- **Second place:** AirPods Max + sponsor credits
- **Third place:** Sponsor credits
- **People's Choice:** AirPods + sponsor credits (hack video with most YouTube views at 5:00pm)

Every attendee walks out with swag.

## Judging criteria

1. **Potential impact** — Does the hack meaningfully improve patient care, clinician experience, or quality of care? Spirit of Agentic Healthcare: intelligent, standards-compliant, automated, even voice-enabled; enhances clinicians rather than adding workload.
2. **Effective use of provided technologies** — How well does the hack use **Deepgram**, **Medplum**, **moss.dev**, and/or **Stedi**?

## Sponsor stack & resources

| Tech | Role | Links | Project skill |
|------|------|--------|---------------|
| Medplum | Headless EHR / FHIR developer platform | [Docs](https://www.medplum.com/docs) · [GitHub](https://github.com/medplum/medplum) | [medplum](../medplum/SKILL.md) |
| Deepgram | STT / TTS / Voice Agent ($200 free credits) | [Docs](https://developers.deepgram.com/home.md) | [deepgram](../deepgram/SKILL.md) |
| Stedi | Eligibility / claims in test mode (no PHI to payers) | [Test mode](https://www.stedi.com/docs/healthcare/test-mode) | [stedi-healthcare](../stedi-healthcare/SKILL.md) |
| Moss | Real-time semantic search (&lt;10ms) for voice agents | [docs.moss.dev](https://docs.moss.dev/docs) | [moss-dev](../moss-dev/SKILL.md) |

When implementing Medplum, Deepgram, Stedi, or Moss, **read the linked skill first**.

Help during the event: [Medplum Discord](https://discord.gg/medplum) → hackathon channel.

## Links

- Sign up: https://events.ycombinator.com/medplum-hackathon-26
- Blog: https://www.medplum.com/blog/yc-medplum-hackathon-2026
- **Submit hack:** https://docs.google.com/forms/d/e/1FAIpQLSdqhh466ADsUm-44CSkjC0xkOcm431wkJx_n_r7W4qT8FCRgA/viewform?usp=header

## Judges (quick context)

- **Diana Hu** — Partner, Y Combinator
- **Cody Ebberson** — Co-founder & CTO, Medplum (YC S22)
- **Ana Yoon Faria de Lima** — Co-founder, Pavoot (YC P26)
- **Naomi Carrigan** — Deepgram community
- **Victor Wang** — Staff SWE, Deepgram (partner platform)
- **Sri Raghu Malireddi** — Co-founder, Moss (YC F25)

## Canonical product (this team)

Read **[docs/PRODUCT_BRIEF.md](../../../docs/PRODUCT_BRIEF.md)** before building. Summary:

**Wearable risk → Deepgram voice → Moss history → Medplum FHIR chart → Stedi eligibility → human handoff** (algorithm aversion / co-regulation).

- Do **not** claim predictive diagnosis; claim risk-triggered triage that frees data from the phone.
- Mock wearables + rule-based risk for the hack; ship one vertical slice by 5:00pm.
- Always offer human escalate; agent prepares the chart so handoff is warm.

## Suggested build patterns (general)

Map product ideas to sponsor tech:

- **Voice intake / ambient charting** → Deepgram (STT) + Medplum (Encounter, Observation, DocumentReference / Composition)
- **History-aware agent** → Medplum patient chart + moss.dev for fast retrieval into the agent loop
- **Cost / coverage before visit** → Stedi eligibility + Medplum Coverage / ExplanationOfBenefit patterns
- **Wearable-triggered outreach (our wedge)** → mock vitals → Deepgram call → Moss + Medplum → Stedi → human handoff
- **n=1 plan + peer review** → Medplum CarePlan / ServiceRequest + review workflow; optional Deepgram voice Q&A

Default bias: one compelling voice → FHIR → action loop that a clinician would trust, demoable live.
