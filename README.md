# YC x Medplum Hackathon

Medplum (S22) is hosting the **Agentic Healthcare Hackathon** at Y Combinator in San Francisco on **Aug 1, 2026**.

Blog: [YC x Medplum Hackathon](https://www.medplum.com/blog/yc-medplum-hackathon-2026)  
Sign up: https://events.ycombinator.com/medplum-hackathon-26  
Submit: [Hack submission form](https://docs.google.com/forms/d/e/1FAIpQLSdqhh466ADsUm-44CSkjC0xkOcm431wkJx_n_r7W4qT8FCRgA/viewform?usp=header)

## About (hackathon theme)

Imagine the doctor's office visit of the future. Prior to your visit, you check in by talking to a voice agent and your conversation is charted for you as it happens, translating into clinical documentation for the experts. Any health issue you describe is deep researched, even if it's just a simple rash and the voice agent tailors the conversation with full context of your history. You receive n=1 treatment that's customized just for you. Your treatment plan is peer reviewed by experts, and your data is visualized to enhance your understanding of the issues at hand. All this happens before you even see a doctor. And of course, you can ask how much treatment will cost ahead of time, and whether your insurance will cover it. That future is voice-first and buildable today, and this is the day to try it.

## What we're building

**Wearable risk → voice check-in → FHIR chart → coverage → human handoff when needed.**

Free consumer wearable signals from the phone; when risk crosses a threshold, a history-aware agent calls, charts into Medplum, checks Stedi eligibility, and escalates to a person for co-regulation — so clinicians get a ready encounter, not another unread alert.

Full problem statement, science, market, Oura/Curry insights, psychology, and demo script:

→ **[docs/PRODUCT_BRIEF.md](docs/PRODUCT_BRIEF.md)**

## Agent stack (building now)

Python LangGraph agent with Medplum + Moss + Deepgram + Stedi + [Open Wearables](https://openwearables.io/docs) (Whoop/Oura/Fitbit/…) hooks — works in `AGENT_MODE=mock` offline:

→ **[agent/README.md](agent/README.md)**

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
