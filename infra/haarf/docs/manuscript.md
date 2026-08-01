# Manuscript Structure

This document describes the structure and content of the HAARF manuscript (`main_updated.tex`), submitted to *npj Digital Medicine* and available as an arXiv preprint.

## File Dependencies

```
main_updated.tex           ← main LaTeX source
HAARF/haarf_references.bib ← BibTeX bibliography (50 entries)
HAARF/*.png                ← figures 1-10 (graphicspath set to HAARF/)
```

Build command: `pdflatex → bibtex → pdflatex → pdflatex`

## Section Outline

| Section | Content | Key Data |
|---------|---------|----------|
| **Abstract** | Framework overview + experimental results summary | N=600 primary + N=120 validation trials |
| **1. Introduction** | AI agents vs traditional AI/ML, three regulatory gaps | 3 gaps identified |
| **1.1 Research Contributions** | Five contributions of this work | Novel framework, 279 requirements, multi-jurisdictional |
| **2. Background** | Evolution of healthcare AI regulation (3 phases) | FDA, EU AI Act, NIST, OWASP AISVS |
| **3. Methodology** | Framework development: stakeholder analysis, mapping, adaptation | 40+ experts, 9 frameworks, 3 phases |
| **4. HAARF Framework** | C1-C8 category details | 279 requirements across 3 levels |
| **5. Framework Analysis** | Visual documentation, risk pillars, regulatory mapping | 8 figures, coverage tables |
| **6. Evaluation Protocol** | Red-team scenario suite, experimental design, metrics | 6 scenarios, 2 conditions, Wilson CIs |
| **7. Results** | Red-team results table, FDA coverage table, cross-framework | Table 4 (main results), Tables 5-6 |
| **8. Discussion** | Paradigm shift, clinical impact, limitations, economics | Model-agnostic claims, future work |
| **9. Conclusion** | Summary of experimental validation | UTSR 56-60% → 0% |
| **Acknowledgments** | 40+ expert contributions by domain | 8 contribution categories |
| **Appendix A** | Complete requirements count by category and level | 85/144/50 = 279 total |
| **Appendix B** | Detailed regulatory framework alignment | 9 frameworks mapped |

## Key Tables

| Table | Label | Content |
|-------|-------|---------|
| 1 | `tab:requirements_summary` | Requirements per category per level |
| 2 | `tab:regulatory_coverage` | Cross-framework coverage percentages |
| 3 | `tab:scenarios` | Red-team scenario suite |
| 4 | `tab:redteam_results` | **Main results** — rates + Wilson CIs |
| 5 | `tab:fda_percategory` | Per-category FDA TPLC alignment |
| 6 | `tab:crossframework` | Cross-framework coverage summary |
| 7 | `tab:metrics` | Metric definitions and targets |
| A1 | Appendix A | Complete category overview |
| B1 | Appendix B | Detailed framework alignment |

## Key Figures

| Figure | File | Content |
|--------|------|---------|
| 1 | `1.png` | Traditional AI pipeline vs AI agent pipeline |
| 2 | `2.png` | HAARF framework overview (8 categories) |
| 3 | `4.png` | Getting started — user paths |
| 4 | `5.png` | Implementation levels (L1/L2/L3) |
| 5 | `7.png` | HAARF requirements by category (visual) |
| 6 | `6.png` | Three-factor risk classification |
| 7 | `10.png` | Resilience architecture |
| 8 | `9.png` | AI agent lifecycle with continuous governance |

## Citations

The manuscript cites 14 unique references from `haarf_references.bib` (which contains 50 total entries). Key citations:

- `haarf2025repo` — project GitHub repository
- `wilson1927probable` — Wilson score CI methodology
- `fda2021aiml`, `eu2024aiact`, `nist2023airisk` — primary regulatory frameworks
- `owasp2024aisvs` — security verification standard foundation

## Experimental Data in Manuscript

All quantitative claims in the manuscript are derived from:

- **Primary run**: `results/` — 600 trials, Gemini 2.5 Flash
- **Validation run**: `results_validation/` — 120 trials, Claude Sonnet 4.6
- **Analysis**: `results/summary.csv` and `results_validation/summary.csv`

The `analyse.py` script reproduces all reported metrics and confidence intervals from the raw trial JSON traces.
