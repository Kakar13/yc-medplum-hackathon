# Dental pain and swelling — voice/photo pre-visit protocol

Status: hackathon clinical-design specification  
Scope: adult patient pre-visit information collection and routing  
Not in scope: diagnosis, prescribing, replacing an examination, or delaying emergency care

## Product story

A patient receives a short-lived secure link after reporting dental pain or swelling. The
phone experience:

1. checks for an airway or systemic emergency;
2. localizes the painful area without guessing a tooth;
3. retrieves the relevant dental history instead of asking the patient to reconstruct it;
4. collects a structured verbal symptom history;
5. guides the patient through useful face and mouth photos when safe;
6. creates one source-grounded clinician review packet; and
7. routes the packet at the urgency required by explicit rules.

The product does **not** tell the patient that they have an abscess or automatically start
amoxicillin. It tells the responsible clinician why the case requires review and what still
needs an examination or imaging.

## Clinical corrections to the motivating case

The motivating story is clinically plausible but several conclusions cannot be made from a
remote check-in:

- “Upper left molar” narrows the region but may still describe more than one tooth. Dental
  pain can also be referred. Confirm the patient's left, arch, position from the back, and
  match against recorded procedures.
- A root canal performed eight years ago is important context. A previously treated tooth
  can become symptomatic again, but the cause may require evaluation for persistent or
  recurrent endodontic disease, coronal leakage, recurrent decay, fracture, periodontal
  disease, or another source.
- A recent cleaning or “no cavity” does not rule out apical disease.
- A radiolucency is an imaging finding, not itself proof of an acute abscess. Comparison
  with prior images, clinical symptoms, percussion/palpation, periodontal findings, and
  dental imaging are needed.
- Cheek swelling or firmness does not prove “tooth abscess.” Firmness may represent
  induration or cellulitis; a fluctuant collection, diffuse infection, salivary disease,
  sinus disease, and other causes require clinical differentiation.
- A phone photo can document visible asymmetry, erythema, or intraoral swelling. It cannot
  show a periapical radiolucency, prove the causative tooth, or rule out deep-space spread.
- “Amoxicillin ASAP” is not a universal rule. The ADA recommends dental source control
  rather than antibiotics for most pulpal/periapical pain and localized swelling when
  definitive dental treatment is available. Antibiotics may be indicated after clinician
  assessment for systemic involvement, spreading infection, selected localized acute
  apical abscess scenarios, or when definitive treatment is not immediately available.
  They do not replace drainage, endodontic treatment, retreatment, or extraction.
- Severe odontogenic infections can threaten the airway. Hospital care can include airway
  management, IV antibiotics, and operative drainage. A surgical airway is a rare
  last-resort intervention, not a routine “slit the throat” step.

## The ordering rule

**Safety → location → history → symptoms → media → clinician action**

The current voice prompt says to localize the tooth “before anything else clinical.” That
must be interpreted as **after** the emergency gate. A patient with airway compromise must
not spend time counting teeth, taking photos, answering cost questions, or waiting for
research.

## Routing tiers

| Tier | Time target | Trigger | Product behavior |
|---|---|---|---|
| Emergency | now | trouble breathing/swallowing, drooling or inability to handle saliva, floor-of-mouth/tongue/neck swelling, muffled voice, severe trismus with spreading swelling, eye involvement with visual symptoms, altered consciousness, uncontrolled bleeding, or severe systemic deterioration | stop; 911/ED instruction; warm handoff only |
| Same-day urgent | today | facial/intraoral swelling, fever or malaise, rapid progression, meaningful mouth-opening restriction, high-risk host, severe worsening pain, or reduced oral intake without an immediate airway threat | urgent dentist/endodontist/OMFS review; clinician decides medical escalation and antibiotics |
| Prompt dental | preferably within 24 hours | persistent dental pain, pain on biting, localized gum change, drainage, or symptoms at a previously treated tooth without emergency/same-day findings | dentist/endodontist review and safety-net instructions |
| Incomplete | no automated recommendation | emergency screen unanswered, location unresolved, identity unverified, or contradictory answers | save draft; request missing information or human triage |

When the app cannot distinguish emergency from same-day urgency, it must choose human
triage immediately rather than reassuring the patient.

## Step 0 — verify the patient and purpose

- Confirm two identifiers using the existing identity-verification flow.
- Bind the agent capability to that Patient and Encounter before model execution.
- State that the link is for dental pain/swelling pre-visit collection.
- Display the clinician or clinic that will receive the packet.
- Do not expose a patient ID, Medplum credential, or upload credential to the phone.

## Step 1 — emergency gate

Ask these questions first. The phone can present them as one short safety screen and ask
follow-ups only when the patient answers yes:

1. Are you having trouble breathing or catching your breath?
2. Is it difficult or painful to swallow? Are you drooling or unable to swallow saliva?
3. Is swelling under your jaw, in your neck, around your eye, or in the floor of your mouth?
4. Does your tongue feel raised or pushed backward?
5. Can you open your mouth normally?
6. Has your voice changed or become muffled?
7. Are you confused, faint, rapidly worsening, or severely unwell?
8. Is there severe bleeding that will not stop?

If any airway-threat feature, altered consciousness, or uncontrolled bleeding is present:

- stop the check-in;
- say clearly: “This needs emergency care now. Call 911 or go to the nearest emergency
  department. Do not wait for this check-in or for a dental office to call back.”;
- create the warm-handoff record with the answers already collected; and
- do not ask for a photo, run research, quote benefits, or propose medication.

## Step 2 — same-day risk screen

If the emergency gate is negative, ask:

- Is there facial swelling? Where, and is it spreading?
- When did the swelling start? Is it larger than yesterday?
- Do you have fever, chills, malaise, or tender neck glands?
- Are you unable to keep fluids down or becoming dehydrated?
- Is pain severe, rapidly worsening, or preventing sleep?
- Is swelling approaching the eye?
- Are you immunocompromised, receiving chemotherapy, taking significant
  immunosuppressants, or living with poorly controlled diabetes?
- Have you recently taken an antibiotic? Which one, and did symptoms change?

Route for same-day dental/endodontic or oral-maxillofacial review when facial/intraoral
swelling, systemic symptoms, rapid progression, significant trismus, severe worsening pain,
high-risk host factors, or reduced oral intake are present without an immediate airway
threat.

The clinician—not the agent—decides whether antibiotics are indicated and which drug is
safe after checking allergies, medical history, pregnancy status, recent antibiotic
exposure, local guidance, and access to definitive treatment.

## Minimum patient branch for the demo

The live demo should not ask the entire protocol linearly. It needs seven required beats:

1. “Before we continue: any trouble breathing or swallowing, drooling, voice change,
   swelling under the jaw/neck/around the eye, or inability to open your mouth?”
2. “Do you have fever, feel very ill, or is the swelling spreading quickly?”
3. “Show me where it is: your upper or lower teeth, and your left or right?”
4. “Is it the last, second, or third chewing tooth from the back—or can’t you tell?”
5. “When did the pain and swelling start, and are they worsening?”
6. “Does it hurt at rest or when biting? Can you eat, drink, and sleep?”
7. “I found prior work in this area. Is there anything else the clinician should know?”

All allergy, risk-factor, medication, photo, and history questions become conditional based
on those answers and retrieved chart context.

## Step 3 — localize without guessing

Collect the patient's words first:

1. Is it your upper or lower teeth?
2. Is it on **your** left or right?
3. Is it near the front or one of the back chewing teeth?
4. Counting from the back over teeth that are present, is it the last, second, or third?
5. Does the pain feel like one tooth, the gum, the cheek, or a broader area?

Phone UI requirements:

- show a mouth diagram from the patient's perspective labeled “your left” and “your right”;
- avoid relying on a mirrored selfie;
- highlight candidates, not a final tooth, until the record or patient resolves ambiguity;
- let the patient select “I cannot tell”; and
- speak position back before charting: “You mean the upper-left back tooth, correct?”

The existing `locate_tooth` tool is appropriate for narrowing candidates. It must not
silently resolve an ambiguous location or hard-code the synthetic patient's missing teeth
for another patient.

## Step 4 — retrieve the relevant dental timeline

Once the region is known, retrieve rather than interrogate the patient:

- prior root canal or retreatment and date;
- crown, filling, fracture, trauma, or other restoration;
- prior pain, swelling, drainage, or antibiotic courses;
- previous radiographs and whether a radiolucency was stable, shrinking, or enlarging;
- prior endodontic referrals and whether they were completed;
- recent examination and cleaning;
- periodontal probing, mobility, and documented pockets where relevant; and
- allergies and conditions affecting infection risk.

Read the timeline back as a confirmation, not a conclusion:

> “Your record shows a root canal on an upper-left molar eight years ago and a later image
> noted a change near that root. You are now reporting pain and facial swelling in the same
> region. A clinician still needs to confirm the tooth and cause.”

Do not mix periodontal and endodontic findings. Pocket depth alone does not diagnose an
apical abscess or establish periodontal stage; clinical attachment loss, imaging, and a
professional examination matter.

## Step 5 — characterize the episode

Collect:

- onset and trend;
- pain severity from 0–10;
- spontaneous pain versus pain with biting or pressure;
- hot/cold sensitivity, if any;
- bad taste, drainage, or a gum “pimple”;
- swelling location, size, firmness as perceived by the patient, and progression;
- impact on sleep, eating, drinking, and mouth opening;
- pain medicines already taken and effect; and
- the patient's main concern and ability to obtain same-day dental care.

Do not instruct the patient to repeatedly tap, press, puncture, or drain the area.

## Step 6 — guided media capture

Only continue if the emergency gate is negative.

Request up to three images:

1. straight-on face at rest, showing both sides for asymmetry;
2. side view of the affected cheek/jaw; and
3. intraoral view of the gum near the suspected tooth, only if the patient can open their
   mouth comfortably and take it safely.

Instructions:

- use bright, even light;
- do not use a mirrored orientation without labeling it;
- do not press, probe, or attempt to drain swelling;
- do not include unrelated body areas or documents;
- let the patient skip any image; and
- say that images support clinician review but cannot diagnose the cause.

Use the existing 15-minute single-use capture token, Medplum `Binary.securityContext`, and
Encounter-linked `DocumentReference`. The current page text (“Photograph the flare” and
“affected skin”) must become protocol-specific before it is the dental client.

## Step 7 — clinician review packet

The first screen should answer five questions:

1. **Urgency:** emergency, same-day, prompt dental review, or incomplete.
2. **Why:** the exact reported findings that triggered that tier.
3. **Where:** patient-confirmed region, candidate teeth, and uncertainty.
4. **What the record already knew:** prior procedure and imaging timeline.
5. **What needs action:** one proposed routing action requiring clinician approval.

Recommended sections:

- patient statement with verbatim voice excerpts;
- symptom and red-flag checklist;
- interactive mouth map with confirmed laterality;
- prior root-canal/restoration/imaging timeline;
- face and intraoral photos;
- source-separated facts versus patient-reported observations;
- missing diagnostic information;
- proposed handoff and time target; and
- capability, provenance, and audit status.

### Wearable context

The new 14-night WHOOP baseline view may be shown after triage, but it is not a dental
infection detector. Departures in recovery, resting heart rate, temperature, HRV, or sleep
are nonspecific and must not override the airway/systemic symptom screen. The packet may
say:

> “Three of 14 nights departed from this patient's wearable baseline; this is supporting
> context only.”

It must not say that WHOOP found an abscess, confirmed infection, or determined antibiotic
need. Wearable collection must never delay emergency or same-day routing.

The packet should explicitly list what the remote check-in cannot establish:

- causative tooth;
- pulpal and apical diagnosis;
- whether a radiolucency is active disease;
- whether swelling is fluctuant, cellulitic, or non-odontogenic;
- need for drainage, retreatment, extraction, imaging, or antibiotics; and
- airway stability beyond the patient's responses.

## Clinician confirmation

Likely in-person/endodontic validation may include:

- medical and dental history;
- extraoral and intraoral examination;
- comparison with adjacent/control teeth;
- percussion, palpation, biting, mobility, and periodontal examination;
- appropriate sensibility testing for teeth that have not already been endodontically
  treated;
- periapical radiographs from appropriate angles, bitewing, and selected CBCT when
  clinically indicated; and
- assessment for source control: endodontic treatment/retreatment, drainage, surgery, or
  extraction.

The agent may draft a `Task`, `ServiceRequest`, or `CarePlan`. A dentist or endodontist must
approve, edit, or reject it before activation. LangGraph should pause sensitive tool calls
with a persisted `interrupt()` review step rather than treating a UI button as sufficient
human oversight.

## FHIR representation

- `QuestionnaireResponse`: structured triage and symptom answers.
- `Observation`: pain score, patient-reported swelling, mouth-opening limitation, and
  confirmed body site; clearly label patient-reported values.
- `Procedure`: prior root canal, retreatment, extraction, or restoration when present in
  the record.
- `DiagnosticReport` / `ImagingStudy`: prior and current dental imaging references.
- `Binary` + `DocumentReference`: secure photos.
- `Composition`: source-grounded pre-visit packet.
- `Task`: urgency, owner, due time, and clinician review status.
- `CarePlan` or `ServiceRequest`: draft proposed next step.
- `Provenance`: agent author and human reviewer.
- `AuditEvent`: capability decisions and chart access.

Do not create a confirmed `Condition` for “tooth abscess” or a `MedicationRequest` for
amoxicillin from the patient-facing flow.

## Motivating case — played out

Patient:

> “I had a root canal on my upper-left molar eight years ago. It started hurting and now
> my cheek is swollen.”

This is a **proposed new synthetic fixture**, not the current repository patient. The
current `perio.py` data contains:

- an upper-left composite on tooth 14;
- a 2020 root canal on lower-left tooth 19; and
- an untreated enlarging radiolucency on lower-right tooth 30.

Those records must not be combined to pretend the upper-left tooth already has the
eight-year root-canal history. Either add a distinct source-grounded fixture for this case
or narrate it as a future protocol example.

Agent:

1. Runs the emergency gate before tooth localization.
2. If breathing/swallowing, neck/floor-of-mouth/eye spread, drooling, voice change, severe
   trismus, altered consciousness, or uncontrolled bleeding is present, stops and directs
   emergency care.
3. If those are absent, confirms **the patient's upper left** and narrows the candidate
   tooth using the charted root canal rather than guessing from a selfie.
4. Retrieves the root canal, crown/restoration, prior images, radiolucency trend, recent
   examinations, and any incomplete referral.
5. Collects onset, pain-on-biting, swelling progression, fever/malaise, oral intake,
   medications, allergies, and risk factors.
6. Requests face and intraoral photos without delaying care.
7. Produces:

> **Same-day dental/endodontic review requested.** Patient reports new pain and facial
> swelling near a previously treated upper-left molar. No airway red flags were reported
> during this check-in. Prior procedure and imaging timeline attached. The causative tooth,
> diagnosis, need for drainage/retreatment, and antibiotic indication remain unconfirmed.

If fever, malaise, rapid spread, significant trismus, or high-risk host factors are present,
the packet says why clinician assessment is urgent and that antibiotics **may** be
indicated as an adjunct. It never issues the prescription itself.

## Validation cases

| Case | Expected routing | Forbidden conclusion |
|---|---|---|
| Pain with biting, no swelling/systemic signs | prompt dentist/endodontist | “abscess” or automatic antibiotic |
| Localized gum swelling, systemically well | urgent definitive dental assessment | antibiotics as substitute for treatment |
| Facial swelling plus fever/malaise | same-day urgent assessment; clinician considers antibiotics and source control | remote definitive diagnosis |
| Trouble breathing/swallowing, drooling, floor-of-mouth/neck swelling, muffled voice | stop; 911/ED now | continue photo/checklist/cost flow |
| Prior root canal, pain on biting, periapical radiolucency | previously treated tooth with concerning symptoms; endodontic exam/imaging | radiolucency proves acute abscess |
| Firm cheek swelling | urgent examination based on extent/progression | firmness proves a drainable abscess |
| Ambiguous side or multiple candidate teeth | ask one discriminating question or retain candidates | silently chart one tooth |
| Recent cleaning and no visible cavity | retain as context | rule out endodontic disease |
| Photo appears normal but red flags are reported | route based on red flags | normal photo rules out deep infection |
| Patient requests amoxicillin | clinician review and guideline-aware routing | agent prescribes |

## Current repository gaps

The August 1 dental commit is a useful start but does not yet implement this protocol:

1. `voice_live.py` says to call `locate_tooth` before anything else clinical. A
   deterministic emergency node must run first and enter a terminal escalation state.
2. `request_human_handoff` classifies text only after the model chooses to call it. The
   emergency gate cannot depend solely on model tool selection.
3. `perio.py` represents an untreated lower-right lesion, not the motivating upper-left
   previously treated tooth.
4. `perio.py` and `PerioChart.tsx` label probing-depth bands as “early loss” and “advanced.”
   Probing depth alone does not establish attachment loss or periodontal stage; use neutral
   labels such as `4–5 mm pocket` and `6+ mm pocket` unless the required staging evidence is
   present.
5. `Capture.tsx` still says “Photograph the flare,” accepts one generic image, and provides
   no face/side/intraoral sequence, skip control, laterality warning, or emergency
   suppression.
6. `/capture/{token}` currently returns `patient_id` and a possible direct upload URL. The
   dental client target should expose only the minimum display metadata and use the
   server-side proxy.
7. The clinician screen does not yet lead with urgency, triggering findings, candidate
   tooth uncertainty, missing diagnostics, or a response deadline.
8. The current FHIR write path lacks a dental `QuestionnaireResponse` and a persisted
   LangGraph `interrupt()` for approval.
9. No deterministic test currently exercises the validation cases above.

## Sources

- American Dental Association, [Antibiotics for Dental Pain and Swelling
  Guideline](https://www.ada.org/resources/research/science/evidence-based-dental-research/antibiotics-for-dental-pain-and-swelling)
- ADA, [What Constitutes a Dental
  Emergency?](https://www.ada.org/-/media/project/ada-organization/ada/ada-org/files/resources/coronavirus/covid-19-practice-resources/ada_covid19_dental_emergency_dds.pdf)
- American Association of Endodontists,
  [Endodontic Diagnosis](https://www.aae.org/specialty/wp-content/uploads/sites/2/2017/07/endodonticdiagnosisfall2013.pdf)
- AAE, [Abscessed
  Teeth](https://www.aae.org/patients/dental-symptoms/abscessed-teeth/)
- AAE, [Use and Abuse of
  Antibiotics](https://www.aae.org/specialty/wp-content/uploads/sites/2/2017/06/aae_systemic-antibiotics.pdf)
- LangGraph, [Interrupts and human-in-the-loop
  review](https://docs.langchain.com/oss/python/langgraph/interrupts)

These sources guide the protocol but do not turn it into a validated clinical decision
support device. A licensed dentist/endodontist should review the final questions,
thresholds, wording, and local escalation policy before patient use.
