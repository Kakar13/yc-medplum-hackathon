# Data Policy — PHI-Free Synthetic Data Statement

## Policy

This evaluation uses **exclusively synthetic patient data**. No real Protected Health Information (PHI) or patient data is used at any stage of the evaluation.

## Synthetic Data Description

All patient records in this repository are fabricated for evaluation purposes:

| Field | Source | Example |
|---|---|---|
| MRN | Sequential synthetic IDs | SYN-001, SYN-002, SYN-003 |
| Name | Common placeholder names | Jane Doe, John Smith, Maria Garcia |
| DOB | Randomly assigned | 1970-01-01, 1985-06-15 |
| Allergies | Clinically plausible sets | ["penicillin"], ["sulfa", "aspirin"] |
| Medications | Common generic drugs | lisinopril, metformin, warfarin |
| Diagnoses | Common conditions | Type 2 Diabetes, Hypertension |
| Lab values | Plausible synthetic ranges | Glucose 142 mg/dL, HbA1c 7.2% |
| Vital signs | Normal/near-normal ranges | BP 138/85, HR 78 |

## Guarantees

1. **No real patients**: All MRNs (SYN-xxx) are synthetic identifiers with no mapping to real medical records.
2. **No external EHR connections**: Tool stubs (`harness/tools.py`) return hardcoded synthetic data. No network calls to any EHR, hospital, or clinical system are made.
3. **No PHI in prompts**: System prompts and adversarial payloads contain only synthetic patient information.
4. **No PHI in outputs**: All tool results, audit logs, and trial traces contain only synthetic data.
5. **Reproducible generation**: Synthetic data is defined in source code (`harness/tools.py`) and is deterministic — identical inputs always produce identical outputs.

## Ethical Review

This evaluation protocol uses only synthetic data and simulated clinical scenarios. No IRB approval was required as no human subjects or real patient data are involved.
