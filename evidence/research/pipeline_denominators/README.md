# Pipeline denominator register

This packet inventories the denominators available at each research-pipeline stage. It keeps separately sourced counts separate: the local data audit, the selected training-only candidate census, archived A4A/A4B policy evaluations, and current matched-baseline arms are different scopes and do not form one joined funnel.

## Local data

The current-byte quality scan covers 39 manifested inputs (8,162,529,858 bytes). It records 2,215,084 bar rows and 172,290,383 tick rows, of which 171,918,993 have finite and non-crossed bid/ask sides in the raw row. The 371,390 rows missing at least one side are excluded from that raw quote count. Nonpositive and inverted raw quote counts are zero.

The current production TickBook builder restores 371,390 rows using independent side carry-forward, retains 172,290,383 rows total, and drops 0. The restored-row count does not imply simultaneous bid/ask availability.

## Feature and candidate census

The selected training-only census reports 351,432 primary-symbol M1 feature rows. Its configured catalog has 108 setup tuples: 24 supported and 84 unsupported by that profile. It records 488,008 supported candidate-row occurrences, with 0 active rows missing required source time. Unsupported tuples are not counted as missing observations or runtime-inactive rows.

## Current matched-baseline development traces

[`current_matched_baseline_flow_summary.json`](current_matched_baseline_flow_summary.json)
adds a separate, manifest-hash-verified scope for the three current matched
baselines on the local 2025 development split. Each arm records 99,492 unique
decision rows, and all open-fill events link to decision IDs in that arm's
trace. The always-no-trade control has no fills or positions. The random arm
has 1,854 open fills/positions and 1,854 terminal positions; the
structure-priority arm has 1,169 of each. Event-ledger row counts and types
remain separate from position counts. Candidate selections and entry
rejections are also recorded per arm.

These artifacts do not record broker order-attempt or accepted-order identities
and statuses; the summary keeps both counts null rather than inferring them
from actions, rejection events, or fills. This current baseline flow does not
recover historical A4A/A4B policy actions or complete the historical
candidate-to-order funnel.

Rebuild the summary from the existing verified bundle with:

```bash
.venv/bin/python -m scripts.research.analysis.evaluation.build_matched_baseline_flow_summary
```

## Archived policy evaluation marginals

| Run partition | Steps | Sessions | Candidate created | Trigger requested / refused | Open fills | Execution rows | Positions | Completed | Orders |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A4A testing | 79069 | 205 | 2885 | 15438 / 1081 | 203 | 411 | 203 | 203 | not recorded |
| A4A training | 99492 | 259 | 1969 | 5785 / 4593 | 987 | 2020 | 987 | 987 | not recorded |
| A4B testing | 79069 | 205 | 2886 | 15473 / 1086 | 203 | 413 | 203 | 203 | not recorded |
| A4B training | 99492 | 259 | 2412 | 9172 / 3845 | 825 | 1678 | 825 | 825 | not recorded |

`trigger requested/refused` are entry-state-machine events, not submitted/accepted broker orders. The historical artifacts do not record order-attempt or accepted-order counts, action-by-session decisions, or a candidate-to-action ID chain. These are marked unavailable, not zero. All position rows in this selected packet are marked completed and reconcile to the recorded closed-position count.

## Interpretation limits

- The rows above are marginal counts with distinct scopes and units; do not divide one stage by another across evidence groups or describe them as conversion rates.
- Candidate row occurrences are not unique decisions, logical events, orders, fills, or trades.
- The evaluation `testing` partition is the exposed 2026-01-01 through 2026-10-16 report period; it is exploratory, not untouched OOS.
- Local counts do not establish provider rights, authoritative time, or external session-calendar facts.
- See `pipeline_denominator_register.json` for hashes, per-input identities, explicit null states, TickBook carry-forward counts, and all four historical run partitions; `pipeline_stage_counts.csv` is the flattened stage inventory. The current matched-baseline summary is deliberately separate.

## Reproduction

Run the generator on the same checkout and local evidence inputs:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.research.analysis.market_data.build_pipeline_denominator_register
```
