# Multiple testing and cost stress contract

**Status:** draft
**Scope:** Trial family, Sharpe input units and fill-ledger reconciliation.

## Inference fields

| Output | Required context | Handling |
|---|---|---|
| Single primary paired-seed result | Predeclared treatment versus always-no-trade, with survival checked first | One-sided sign-flip, exact through 15 pairs and otherwise 100,000 draws with RNG seed 42 under the prospective protocol. |
| Holm-adjusted p-value | A declared family of tests | General paired-seed output adjusts the supplied metrics together. The single-primary path records no adjusted p-value. |
| Expected maximum Sharpe | Number of compared configurations and cross-trial Sharpe dispersion | Zero benchmark for one or fewer trials or nonpositive dispersion. |
| Deflated Sharpe probability | Per-observation Sharpe, benchmark, observation count, skew and non-excess kurtosis | Undefined for at most one observation or a nonpositive variance term. |

## Cost stress records

| Field | Requirement |
|---|---|
| Scenario | Quote source, sizing, account rules, charges, date window and the declared assumption changed |
| Fill and position evidence | Ordered entry and exit records, position identity, explicit completion and required quote and charge fields |
| Reconciliation residual | Midpoint gross PnL minus spread cost, slippage cost, commission and recorded net PnL |
| Reconciliation status | `matched` within tolerance, `mismatch` for a failed cashflow identity, `unavailable` with a reason for missing or invalid evidence, or `no_completed_positions` |
| Account outcomes | Preserve breaches, missing quotes, skipped orders, open remainder and period role for each scenario |

Only completed positions contribute to the decomposition. Entry costs are
allocated across realized closes. Quote and cost sensitivity of an account
path requires scenario replay under the declared assumptions.

Sources are `evaluation/metrics/deflated_sharpe.py`,
`evaluation/reporting/cost_decomposition.py`,
`scripts/research/analysis/evidence/analyze_paired_seed_results.py` and
`config/research/prospective_research_protocol.yaml`.
See the [subject guide](../../subjects/E_evaluation_research/multiple-testing-cost-stress.md).
