# Baseline Configuration

Defines what is included and excluded in the **baseline** experimental condition.

## Purpose

The baseline condition represents a standard Anthropic tool-use agent **without** HAARF middleware enforcement. It serves as the comparator to demonstrate the safety improvements provided by the HAARF framework.

## Inclusions (Active in Baseline)

| Component | Description |
|---|---|
| Anthropic tool-use loop | Full agent loop with tool calling via `client.messages.create()` |
| Tool schema validation | Tool inputs are validated against JSON schemas by the Anthropic API |
| Tool execution | Stub tools execute and return synthetic results |
| Audit logging | All tool attempts are logged (who, what, when) for trace completeness |
| System prompt | Clinical agent role and patient context are provided |
| Paraphrase selection | Seed-controlled prompt variation for reproducibility |

## Exclusions (Disabled in Baseline)

| HAARF Layer | Controls | What It Does | Why Excluded |
|---|---|---|---|
| RBAC gate | C8.1.1, C8.1.2, C8.4.1 | Denies tool calls not in `tool_permissions` | Tests whether the agent self-limits without enforcement |
| Contraindication gate | C8.2.1, C8.2.2, C8.2.4 | Checks allergies/drugs before medication orders | Tests whether the agent catches contraindications without middleware |
| Injection sanitizer | C3.2.1, C3.2.3, C8.4.4 | Strips instruction-like patterns from tool output | Tests whether the agent resists injection without sanitization |
| Circuit breaker | C8.4.2, C8.5.1, C8.5.2 | Limits consecutive failures, enforces backoff | Tests whether the agent self-limits retry behaviour |

## Implementation

In `harness/middleware.py`:
- `baseline_middleware()`: logs all attempts, allows all tool calls
- `haarf_middleware()`: applies all five enforcement layers before allowing

The condition is selected via `runner.py --condition baseline` or `--condition haarf`.

## Rationale

This design ensures a fair comparison:
- Both conditions use the **same** model, temperature, seed, system prompt, and scenarios.
- The **only** difference is whether the five HAARF enforcement layers are active.
- Audit logging is active in both conditions to ensure trace completeness is measurable.
