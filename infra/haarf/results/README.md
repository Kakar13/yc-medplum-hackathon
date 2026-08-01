# Results Directory

This directory stores per-trial JSON traces and summary CSV produced by the evaluation harness.

## Contents (after running)

```
results/
  RT-1_baseline_0000.json   # Per-trial trace files
  RT-1_baseline_0001.json
  ...
  RT-6_haarf_0049.json
  run_summary.json           # Batch run metadata
  summary.csv                # Metric aggregation with 95% CIs
```

## Generating Results

```bash
# Full batch (all scenarios, both conditions, N=50 trials)
python runner.py --scenario all --condition baseline haarf \
                 --trials 50 --seed 0 --output results/

# Compute metrics
python analyse.py --results results/ --output results/summary.csv
```

## Trace Format

Each per-trial JSON trace contains:
- `config`: Model name, temperature, max_tokens, seed
- `scenario_id`: RT-1 through RT-6
- `condition`: baseline or haarf
- `messages`: Full conversation history
- `tool_attempts`: All tool calls with allow/deny decisions
- `audit_log`: Structured audit entries with required fields
- `pass_criteria_results`: Per-criterion pass/fail
- `passed`: Overall trial pass/fail
- `timing`: Wall-clock execution time

## For Reviewers

If full run logs are too large for the repository, a stratified sample (2 trials per scenario per condition = 24 traces) plus the `summary.csv` will be provided. Full logs are available as a release asset or upon request.

To regenerate from scratch:
```bash
make setup && make run && make analyse
```

Expected runtime: ~30 minutes for N=50 (3,000 API calls). Estimated cost: ~$15 USD at current Anthropic pricing.
