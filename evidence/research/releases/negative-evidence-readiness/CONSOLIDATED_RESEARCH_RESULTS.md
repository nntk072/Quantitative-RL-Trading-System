# Consolidated research results

## Research question and scope

The current research asks whether causal multi-timeframe market context and a
setup-conditioned sequential policy can improve decisions under the project's
execution and account-risk constraints. Existing results are development and
exploratory evidence; they do not establish an untouched out-of-sample claim.

## Selected matched pair

The seed-50 A4A/A4B run identity is retained: two million requested training
steps, 32 environments, and the 2024-12-30 through 2025-12-31 interval. The
archived resolved configurations declare the `env.entry_state_observation`
contrast. Performance, survival, and derived trade-outcome summaries from this
pair are withdrawn from current results presentation. The original source
snapshot, run manifests, configurations, and evidence packets remain for
provenance and reproducibility only. No current performance comparison or
policy-selection claim is made from this pair.

## Earlier policy screens

The tracked 100k-step hybrid and setup-conditioned full-training-period
replays both breached the configured $10,000 maximum-loss gate. The hybrid
control ended at $90,003.73 over 308 positions; the setup-conditioned policy
ended at $90,026.53 over 1,031 positions. These were one-seed negative screens,
not 2M results or confirmation. Their full-year ledgers record no new opens
after the breach.

## Current-source Tier 0 setup reference

The matched setup evaluator completed the 2025 development split for the
always-no-trade control, one seeded random-eligible reference, and one fixed
structure-priority rule. Each arm processed 351,432 bars and 99,492 decisions
from the same bar, feature, and TickBook inputs. The control remained at
$100,000 with no fills or breaches. The random reference completed 1,854
positions, returned −10.16%, and recorded 25 breach events; the fixed rule
completed 1,169 positions, returned −10.03%, and also recorded 25 breaches.
Per-arm and step-aligned paired within-trajectory intervals are retained in
the [matched setup baseline packet](../../matched_setup_baselines/README.md).
These are negative Tier 0/Tier 1 accounting results, not a comparison with the
historical RL checkpoint, multi-seed estimates, or viable strategy claims.

## Exposed report period

The 2026-01-01 through 2026-10-16 interval was previously inspected and is
report-only. Seed-50 A4A/A4B replay outcomes are withdrawn from current results
presentation and cannot be relabeled as a fresh holdout by rerunning them.

## Configured multi-timeframe data

The configured native-versus-M1 bar audit found exact timestamp and OHLCV
parity across 30 native symbol/timeframe series: 532,350 development rows and
423,018 exposed-report rows. US100 D1 is an M1-derived fallback in each split,
so those two views are not independent native comparisons. Native spread
differs from both M1 mean and last-value references; the audit does not infer
which spread definition is authoritative. The first-M1 availability report
records 15 final higher-timeframe rows per period without a later M1 row and
does not classify delayed rows against an authoritative schedule. This bar
result does not resolve tick-side missingness, same-time quote chronology,
feature-prefix coverage, or execution parity. See
[configured multi-timeframe data alignment](../../../../docs/research/multitimeframe_data_alignment.md)
and its [machine report](configured_timeframe_parity.json).

## Candidate outcome-data feasibility

The training-only conditional replay covers 54,638 statically eligible
proposals across the 24 candidate categories enabled by the recorded profile,
with 1,067,731 proposal/bracket combinations. It verified 259,358
filled/resolved rows, 39,186 unfilled/expired limit rows, and 769,187
unresolved rows. Most unresolved outcomes reflect incomplete local quote
coverage before exit resolution (355,861 rows) or order disposition (319,870);
89,609 more have no market-entry quote within the configured wait. The
remaining unresolved rows retain invalid realized stop/target geometry,
session-close boundary, or quote-order failures.

Coverage is strongly unequal by signal month: unresolved shares are 84.8%–94.2%
from 2024-12 through 2025-08, 53.0% in September, 45.4% in October, 32.1% in
November, and 15.9% in December. The candidate-by-month and monthly reason
tables preserve their exact denominators. This pattern is a coverage and
trigger-horizon limitation; it does not identify an economic regime effect.
The stratified replay audit exactly reproduces 12 rows through the same
versioned execution function, not an independent implementation. The packet is
conditional fixed-entry evidence and excludes policy actions, account state,
portfolio contention, and policy value. The current resolved subset is not a
representative basis for candidate calibration, model fitting, or a return
claim. See the [candidate outcome packet](../../candidate_outcomes/README.md).

## Conclusion

No tested model has demonstrated a robust economic edge under the recorded
risk constraints. There is one selected seed-50 pair, no untouched confirmatory
period, and bounded current-source tick and configured-bar audits rather than
an exhaustive data/feature/execution audit.
The underlying provider and license were not investigated at the user's
direction; raw data is excluded and no rights claim is made. The defensible
conclusion is negative and bounded: the
tested policies did not establish viability. Differences between arms remain
descriptive, not causal.

## Canonical result routes

- [Research findings map](../../../../docs/research/README.md) (research-wide)
- [Monthly entry and exit attribution](../../../../docs/research/entry_and_exit_attribution.md)
- [Setup-conditioned 100k replay](../../../../docs/research/setup_conditioned_policy_replay.md)
- [Result registry](../../../../docs/reproduce/result_registry.md)
- [Operational evidence and gates](../../../../docs/operations/research_execution_plan.md)
