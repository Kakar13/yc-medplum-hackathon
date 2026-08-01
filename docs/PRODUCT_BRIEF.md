# Product brief — Preflight

YC x Medplum Agentic Healthcare Hackathon · Aug 1, 2026
**Preflight** (was FlareCheck / PreChart / PulseCheck)

---

## One-liner

**The pre-visit agent you can let write to a chart.** Preflight talks to a patient before their
appointment, charts the conversation as it happens, researches the complaint against real
literature, drafts an n=1 plan for a clinician to approve, and answers "what will this cost" —
with every single action bound to one patient by its authorization, and every decision written
to an audit log.

The demo is the pre-visit flow. The thing that makes it defensible is the layer underneath:
**the subject of care is not the model's to choose.**

---

## Problem statement

Clinical agents are about to be given write access to charts. The tooling to decide whether
that is safe does not exist.

This is not a hypothetical. Medplum's MCP integration exposes a `fhir-request` tool annotated
*"this tool can modify data"* whose schema takes a model-authored URL string — so the patient
whose record gets written is a substring of text a language model composed. Get that wrong and
you have not produced a bad answer, you have produced an order on the wrong person.

The field has measured the problem and not solved it. [HAARF][haarf] red-teams six scenarios
across five middleware layers; its wrong-patient scenario (RT-4) passes 6% with enforcement on
versus 16% baseline — enforcement makes it *worse*, because none of the layers binds the
subject of care. Worse still, its contraindication gate reads allergies from the session
patient while the order names a different MRN, so a wrong-patient order gets safety-checked
against the wrong chart.

Meanwhile the body meant to own assurance collapsed: CHAI's national AI assurance lab network
[failed by early 2025][chai], with leadership conceding they had wrongly assumed
pre-procurement testing mattered more than post-deployment monitoring.

**Slide line:** Everyone is building agents that write to charts. Nobody can prove they wrote
to the right one.

---

## What we are / are not claiming

| Say | Don't say |
|-----|-----------|
| Patient binding enforced by authorization | We solved AI safety |
| Drafts a plan a human commits | Autonomous treatment |
| Retrieved citations, or none at all | Generated references |
| Verifies a published framework's measured gap | We are a certification body |
| All four sponsors live, Medplum in mock | Production-ready today |

---

## Why this gap and not another

We deliberately checked whether the obvious ideas were taken. They are.

| Idea | Why we didn't build it |
|------|------------------------|
| Symptom triage / checker | A graveyard. K Health [shut down its DTC AI care offering][khealth] to pivot to health systems |
| Ambient scribing | Commoditized from above — Epic AI Charting ships February 2026, on top of Abridge at ~$5.3B |
| Outbound payer calling | A knowledge-graph moat, not a weekend build — [Infinitus][infinitus] has 5M+ calls |
| Prior authorization | $200M+ funded incumbents |
| Price transparency | Turquoise shipped [personalized estimates as an API][turquoise] two days before this hackathon |

What is genuinely unbuilt is a verification and enforcement layer for agent FHIR writes. The
academic work near it measures capability, never authorization:

| Work | Covers | Doesn't |
|------|--------|---------|
| [HAARF][haarf] | 279 requirements, 6 red-team scenarios, real measurements | No patient-identity layer; RT-4 unsolved; dict stubs, no FHIR server |
| [HealthAdminBench][hab] (Stanford) | 135 admin tasks, 1,698 verifiable subtasks | Administrative, not clinical write authorization |
| [FHIR-AgentEval][fae] | 43 tasks against resettable HAPI via MCP | Task success, not patient-boundary safety |
| [MedAgentBench][mab] / HealthBench | EHR tasks, clinical Q&A | Capability, not permission |

Every one asks *did the agent succeed*. None asks *was it allowed to*.

**And the sponsor's own docs describe the hole.** Medplum's [Build with AI][medplum-ai] page
states the thesis outright — *"the barrier to production isn't the AI model; it's the lack of a
secure, auditable foundation"* — names the *"can suggest, but not act"* pattern, and requires
an `AuditEvent` for every AI action. It documents the principle and ships no way to verify it
holds. Preflight is that verification.

---

## Hackathon fit

From the [YC x Medplum brief][brief]: voice-first, charted as it happens, deep-researched,
history-aware, n=1, peer-reviewed, visualized, cost known up front.

| Brief requirement | Implementation |
|---|---|
| Check in by talking to a voice agent | Deepgram Nova-3 → LangGraph (`/voice/turn`) |
| Charted as it happens | `Encounter` + `Observation` + `Composition` |
| Any issue deep researched | Europe PMC; retrieved citations only, never generated |
| Full context of your history | Moss hybrid retrieval, with a relevance floor so absent history reads as absent |
| n=1 treatment | `CarePlan` with per-patient reasoning and attached evidence |
| Peer reviewed by experts | `status: draft` + `Task` + `Provenance`; a human commits at `/review` |
| Data visualized | Wearable Observations as gauges against reference ranges |
| Cost and coverage up front | Live Stedi 271 parsed to "$15 copay for an office visit" |
| *(unstated, load-bearing)* | Patient-scoped capability gateway + `AuditEvent` per decision |

### Sponsor use — all four live

| Sponsor | Role | Status |
|---------|------|--------|
| **Medplum** | FHIR CDR; SMART `patient=<id>` scope is what makes binding enforceable server-side rather than a rule we remembered to write | live (mock fallback) |
| **Deepgram** | Nova-3 STT; word-perfect on test utterances at 0.99977 confidence | live |
| **Moss** | Hybrid retrieval over the patient's record, mid-conversation | live |
| **Stedi** | Real-time eligibility (X12 270/271) in test mode | live |

### End-to-end flow

```mermaid
flowchart TD
  P[Patient voice] --> DG[Deepgram Nova-3 STT]
  DG --> A[LangGraph agent]

  S[/session/start] ==>|binds capability<br/>before any model token| CAP{{Capability<br/>patient · purpose · tools}}
  CAP -.->|adjudicates every call| A

  A <--> MOSS[Moss retrieval<br/>score floor 0.75]
  A --> RES[Europe PMC<br/>reviews + guidelines]
  A --> ST[Stedi eligibility]

  A -->|charted as spoken| FH[(Medplum FHIR)]
  A -->|draft only| CP[CarePlan status=draft<br/>+ Provenance + Task]

  CAP ==>|allow / deny| AUD[(AuditEvent ledger)]

  CP --> REV[Human clinician /review]
  REV -->|commits| ACTIVE[CarePlan active]
  REV -->|rejects| VOID[revoked]

  A --> RF{Red flag?}
  RF -->|chest pain, stroke| E911[Say: call 911]
  RF -->|exertional dyspnea| URG[Say: seen today]
  RF -->|no| DONE[Chart ready before the visit]
```

The double lines are the point: the capability is issued by the server and adjudicates every
tool call, and nothing the agent writes becomes care without a human.

---

## Demo script (90 seconds)

1. **Intake** — "My right knee has been swollen and painful for three weeks after I started
   running, worse going downstairs." Charted as it's spoken.
2. **History** — Moss retrieves the patient's own record. Ask about a knee and the eczema
   history correctly does *not* appear; ask about asthma and it does.
3. **Research** — real Europe PMC guidelines for the complaint, not generated references.
4. **Plan** — a draft `CarePlan` with `Provenance` naming the agent as author. It is a
   proposal, not care.
5. **Cost** — live Stedi: *"AETNA INC — active coverage; $15 copay for an office visit; $0
   deductible remaining."*
6. **Review** — clinician opens `/review`, reads the evidence, commits. Now it's active.
7. **Red team** — press the button that asks the agent to order a medication for a *different*
   patient. Denied, with the reason and an `AuditEvent`. Then `/trust` shows the HAARF
   scorecard: 5/5 correct, plus 8/8 on Medplum-MCP-shaped `fhir-request` calls where the
   patient hides inside a URL.

Step 7 is the one to linger on. Everything before it is the brief; step 7 is why it's safe.

**Sample patients:** [Synthea][synthea]-shaped bundles in `agent/data/synthea/`. Both eczema
and asthma bundles are merged, so retrieval is not single-condition.

---

## Evidence

### Agent governance

- [HAARF][haarf] — the framework we score against, and whose RT-4 gap we close
- [Medplum: Build with AI][medplum-ai] — *"can suggest, but not act"*, `AuditEvent` per action
- [Medplum MCP][medplum-mcp] — the `fhir-request` tool our gateway sits in front of
- [CHAI assurance labs collapse][chai] — why post-deployment verification is the unmet need
- [NEJM AI MedAgentBench][mab] — FHIR-native agents are not autonomous-ready
- [Lancet — Zou & Topol][lancet] — agentic AI as teammates

### Wearables as an input (secondary in this build)

- [Nature Medicine — Snyder et al.][snyder]: ~80% of COVID cases flagged at or before symptoms, ~3 day median lead
- [Nature Medicine — DETECT][detect]: sensors plus symptoms beat symptoms alone
- [Nature Sensors — closed-loop wearables][clwbe]: value comes from sense + decide + act + **human oversight**
- [Sumbul Desai (Apple VP Health)][desai]: notifications aren't diagnoses; **actionability**; enrich the encounter rather than adding busywork

### Free the data from the phone

[The Preprint — Neel Shah × Chris Curry][curry]. Dr. Chris Curry (OB/GYN, MD/PhD) went from
Apple cycle tracking to Clinical Director, Women's Health at Oura.

- Wearable data must not end on the phone; EHR + wearable = **one health identity**
- Clinicians recoil from uncurated phone dumps — the need is **interpretation**
- Additive only when it changes the opinion (palpitations plus resting HR 140); skip it when
  the clinical picture is already clear
- Ideal filter catches pathology *and* says "this variation is normal"

Preflight's version of that filter is the retrieval score floor: absent history should read as
absent, not as a low-confidence guess.

---

## Human psychology — design for handoff

People bypass agents to reach a human for calm and trust. Don't fight it; route around it.

| Term | Meaning |
|------|---------|
| **Co-regulation** | Nervous-system calming via another human — bots validate, humans co-regulate |
| **Algorithm aversion** | Humans preferred for consequential medical decisions |
| **Emotional trust** | Belief that someone cares and is accountable |
| **Reassurance-seeking** | Anxiety drives the need for trusted confirmation |

**Product rules learned the hard way in testing:**

- One-tap "talk to a person", always available. AI narrows; humans decide and soothe.
- **A handoff must say the urgent thing out loud.** Our agent recognized a possible heart
  attack, passed it as the handoff reason, and then told the patient only "please stay on the
  line" — the urgency never reached the words. Fixed.
- **Escalation needs tiers.** One tier sent a ten-day cough to an ambulance. Telling every
  escalation to dial 911 teaches patients to ignore it.
- **A failed handoff must not look successful.** Persisting conversation context was wrapped in
  `except: pass`, so a clinician could inherit a patient with none of the conversation.

---

## Market

| Layer | Signal |
|-------|--------|
| Ambient clinical AI | ~$600M+ category revenue; Abridge ~$5.3B — proves clinics pay for voice, and that the niche is closed |
| Agent assurance / eval | No funded incumbent. CHAI's labs failed; benchmarks are academic |
| US RPM | ~$14–16B (2024–25) → ~$29B by 2030 ([MarketsandMarkets][mm]) |
| Consumer wearables | Apple hypertension notifications; Whoop EHR sync; Oura women's health |

**Wedge:** the enforcement and verification layer for clinical agent writes — patient binding,
an audit ledger, and a red-team scorecard — sold to whoever is about to hand an agent write
access. Every platform adopting MCP acquires this problem on the day they enable it.

**ICP:** digital health builders on Medplum first (they hit it first), then health-system
innovation teams, then the payers and regulators who will eventually require the evidence.

---

## Honest limits

- Binding uses identifier heuristics; a patient referenced only by name, or by an identifier
  system the gateway hasn't been told about, would be missed. Production should resolve
  references through the server.
- MCP results adjudicate request *shapes* from Medplum's documented schema; we don't run a live
  MCP server in the loop.
- Medplum runs in mock mode without credentials. The SMART-scope argument is documented and
  correct, but not exercised against a live server here.
- Red-flag detection is keyword-tiered — auditable, but it will miss phrasing we didn't
  anticipate. This should be a model judgement with a keyword floor.
- Retrieval knows two conditions (18 documents). It correctly returns nothing for a third.
- Moss allows 3 indexes on this account, which constrained short-term session persistence.

---

## Pitch (30 seconds)

> Everyone is about to give AI agents write access to medical records. Medplum's own MCP server
> exposes a tool that can modify any patient's chart, where the patient is a string the model
> writes. HAARF measured that exact failure and their middleware made it *worse* — 6% versus
> 16% baseline — because nothing binds the subject of care. Preflight is a pre-visit agent that
> does the whole brief: talks to you, charts as you speak, researches your complaint against
> real guidelines, drafts a plan a doctor approves, tells you it's a $15 copay. And it cannot
> touch anyone else's chart, because the patient is a property of its authorization, not an
> argument it chooses. Ask it to order a drug for another patient and it refuses, in the audit
> log, every time.

---

## Related project files

- **Governance thesis + scorecard:** [`AGENT_GOVERNANCE.md`](AGENT_GOVERNANCE.md)
- **Agent API:** [`../agent/README.md`](../agent/README.md)
- **Web UI:** [`../web/README.md`](../web/README.md)
- **Closed-loop wearable synthesis:** [`CLOSED_LOOP_SYNTHESIS.md`](CLOSED_LOOP_SYNTHESIS.md)
- Skills: Medplum / Deepgram / Stedi / Moss / Open Wearables under [`.cursor/skills/`](../.cursor/skills/)

[haarf]: https://github.com/Task-force-for-AI-agents-in-Healthcare/haarf
[medplum-ai]: https://www.medplum.com/docs/ai
[medplum-mcp]: https://www.medplum.com/docs/ai/mcp
[chai]: https://www.fiercehealthcare.com/ai-and-machine-learning/inside-chais-failed-assurance-labs
[hab]: https://github.com/som-shahlab/health-admin-bench
[fae]: https://github.com/YoussefMkst/FHIR-AgentEval
[mab]: https://ai.nejm.org/doi/full/10.1056/AIdbp2500144
[khealth]: https://exitsandoutcomes.com/k-health-shuts-down-dtc-clinic-big-employer-customer-wins-losses/
[infinitus]: https://www.prnewswire.com/news-releases/infinitus-systems-raises-51-5-million-series-c-funding-on-the-strength-of-ai-guardrails-302283847.html
[turquoise]: https://turquoise.health/api/docs/personalized-estimates/
[brief]: https://www.medplum.com/blog/yc-medplum-hackathon-2026
[synthea]: https://mitre.github.io/fhir-for-research/modules/synthea-overview
[lancet]: https://pubmed.ncbi.nlm.nih.gov/39922663/
[snyder]: https://www.nature.com/articles/s41591-021-01593-2
[detect]: https://www.nature.com/articles/s41591-020-1123-x
[clwbe]: https://www.nature.com/articles/s44460-026-00105-4
[desai]: https://medicine.stanford.edu/news/stories/2025/09/sumbul-desai-mgr.html
[curry]: https://open.spotify.com/episode/64oyP3yA5QLBvby0Cvqkqe
[mm]: https://www.marketsandmarkets.com/Market-Reports/us-remote-patient-monitoring-rpm-market-252862303.html
