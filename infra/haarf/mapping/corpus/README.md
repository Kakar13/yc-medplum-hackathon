# Mapping Corpus Provenance

This directory documents the regulatory framework sources used for the HAARF coverage mapping analysis. The actual regulatory documents are not redistributed due to copyright; instead, we provide citations, versions, and access instructions so reviewers can independently obtain the same corpus.

## Source Documents

### 1. FDA Digital Health / Total Product Lifecycle (TPLC)
- **Title:** Artificial Intelligence and Machine Learning (AI/ML)-Enabled Medical Devices — FDA
- **Version:** Action Plan (January 2021) + Marketing Submission Recommendations for a Predetermined Change Control Plan for AI/ML-Enabled Device Software Functions (September 2023)
- **Access:** https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-aiml-enabled-medical-devices

### 2. EU AI Act
- **Title:** Regulation (EU) 2024/1689 — Artificial Intelligence Act
- **Version:** Official Journal of the European Union, 12 July 2024
- **Access:** https://eur-lex.europa.eu/eli/reg/2024/1689/oj

### 3. Health Canada SGBA+
- **Title:** Guidance Document: Pre-Market Requirements for Medical Device Cybersecurity + SGBA+ Framework
- **Version:** Version 1.0 (2023)
- **Access:** https://www.canada.ca/en/health-canada/services/drugs-health-products/medical-devices.html

### 4. UK MHRA AI Airlock
- **Title:** Software and AI as a Medical Device Change Programme — AI Airlock Regulatory Sandbox
- **Version:** 2024 guidance
- **Access:** https://www.gov.uk/government/publications/software-and-ai-as-a-medical-device-change-programme

### 5. NIST AI Risk Management Framework (AI RMF)
- **Title:** Artificial Intelligence Risk Management Framework (AI RMF 1.0)
- **Version:** NIST AI 100-1, January 2023
- **Access:** https://www.nist.gov/artificial-intelligence/executive-order-safe-secure-and-trustworthy-artificial-intelligence

### 6. OWASP AISVS
- **Title:** AI Security Verification Standard (AISVS)
- **Version:** v1.0 (2024)
- **Access:** https://owasp.org/www-project-ai-security-verification-standard/

### 7. WHO GI-AI4H
- **Title:** Ethics and Governance of Artificial Intelligence for Health — WHO Guidance
- **Version:** 2021
- **Access:** https://www.who.int/publications/i/item/9789240029200

### 8. ISO/IEC 42001
- **Title:** Information Technology — Artificial Intelligence — Management System
- **Version:** ISO/IEC 42001:2023
- **Access:** https://www.iso.org/standard/81230.html

### 9. IMDRF GMLP
- **Title:** Machine Learning-enabled Medical Devices: Key Terms and Definitions — Good Machine Learning Practice
- **Version:** IMDRF/AIMD WG/N67 (2022)
- **Access:** https://www.imdrf.org/documents/machine-learning-enabled-medical-devices-key-terms-and-definitions

## Reproduction Instructions

1. Obtain each document from the URLs above (or your institution's regulatory library).
2. Use `mapping/rubric.md` for match-type definitions (EM/PM/NM).
3. The row-level coding is in `mapping/coding_sheet.csv`.
4. Run `python mapping/compute_coverage.py` to reproduce the coverage percentages.
