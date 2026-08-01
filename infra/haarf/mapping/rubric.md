# HAARF Regulatory Mapping Rubric

## Match Type Definitions

Mappings between HAARF requirements and external regulatory framework clauses are coded using three categories:

### EM — Exact Match
The HAARF requirement directly corresponds to a specific clause in the regulatory framework, with equivalent scope, intent, and level of specificity.

**Criteria:**
- Same subject matter and regulatory intent
- Comparable specificity and actionability
- Direct traceability between requirement and clause

**Example 1:** HAARF C1.1.1 (Three-Factor Risk Assessment) → FDA TPLC Risk Framework (clinical function, autonomy level, data sensitivity). Both require multi-dimensional risk classification for AI/ML medical devices with comparable factors.

**Example 2:** HAARF C8.1.1 (Role-Based Tool Authorization) → EU AI Act Article 9(4)(b) (access control for high-risk AI). Both mandate role-based access controls for AI system functions with enforcement mechanisms.

### PM — Partial Match
The HAARF requirement addresses the same general domain as a regulatory clause, but differs in scope, specificity, or healthcare-specific adaptation. The external framework addresses the topic but not with the same granularity or healthcare focus.

**Criteria:**
- Overlapping subject matter with differences in scope or depth
- One requirement is more specific or healthcare-adapted than the other
- General regulatory principle maps to specific HAARF implementation

**Example 1:** HAARF C3.2.1 (Healthcare-Specific Prompt Injection Detection) → OWASP AISVS 8.2 (General Input Validation). OWASP addresses input validation generically; HAARF specifies healthcare-targeted injection patterns (e.g., clinical instruction manipulation).

**Example 2:** HAARF C7.1.1 (Intersectional Fairness Assessment) → Health Canada SGBA+ (Sex and Gender-Based Analysis). Health Canada requires demographic analysis; HAARF extends to intersectional fairness across multiple clinical dimensions.

### NM — No Match
The HAARF requirement addresses a domain not covered by the regulatory framework, or the framework has no analogous provision.

**Criteria:**
- No corresponding clause in the regulatory framework
- The regulatory framework does not address this domain
- The HAARF requirement represents a novel healthcare AI-specific need

**Example 1:** HAARF C8.4.2 (Clinical Circuit Breaker for Tool Failures) → FDA TPLC: No match. FDA guidance does not address autonomous agent tool-use failure cascade prevention.

**Example 2:** HAARF C6.3.1 (Multi-Agent Coordination Governance) → EU AI Act: No match. The EU AI Act does not address coordination between multiple autonomous AI agents operating in clinical settings.

## Coding Instructions

1. For each HAARF requirement, identify the most relevant clause(s) in the target framework.
2. Assign EM, PM, or NM based on the criteria above.
3. Record a brief rationale explaining the match decision.
4. When multiple clauses partially match, select the strongest match and note alternatives.
5. When in doubt between PM and NM, default to NM (conservative coding).

## Coverage Computation

Coverage percentage per framework = (EM + PM) / Total HAARF requirements × 100

Only EM and PM contribute to coverage; NM indicates a gap where the external framework does not address the HAARF requirement.
