# Session equity daily-loss screen

This screen applies the current 5% initial-equity daily-loss allowance to the
preserved A4A/A4B training and report-period equity observations. It uses the
current local source data only and does not rerun either policy.

## Method and scope

The audit verifies each saved run config against its reanalysis manifest, then
verifies the configured M1 source row count, unique timestamps, and bounds
against the processed-bar manifest. It maps equity observations to the
source-local date labels that define the supplied session IDs. Exact M1
timestamps are used when present; sub-bar execution timestamps use the same
date's verified label. Every equity date mapped, with zero missing dates.

The account starts at the configured initial balance for its first observed
session. At later session transitions, the session opening anchor is the
previous equity observation. This matches the pinned environment implementation
at source commit `258bed03ebec87698feaf14a3fa8a0cfc7d965ce`, which resets daily
before marking the first bar of the new supplied session. The threshold is
`initial_balance × 0.05`; for the saved $100,000 accounts that is $5,000. A
sample breaches the daily floor only when equity is strictly below the floor;
equality is allowed.

| Arm and partition | Equity samples | Sessions | Exact M1 timestamps | Sessions below $5,000 floor | Largest observed session loss |
|---|---:|---:|---:|---:|---:|
| A4A training | 99,493 | 259 | 98,403 | 0 | $4,972.04 on 2025-04-04 (session 68) |
| A4B training | 99,493 | 259 | 98,567 | 0 | $4,473.28 on 2025-05-01 (session 86) |
| A4A report period | 79,070 | 205 | 78,846 | 0 | $3,447.45 on 2026-01-06 (session 2) |
| A4B report period | 79,070 | 205 | 78,845 | 0 | $3,388.30 on 2026-01-06 (session 2) |

The historical gross realized-loss counter events in training session 47 are
also visible in the equity series. A4A's largest sampled session loss there is
$3,004.28; A4B's is $3,389.32. Those events were recorded when accumulated
negative close PnL crossed $5,000, without offsetting winning closes. Their
recorded event values did not breach the 5% session-net equity floor.

## Interpretation limits

These are serialized account-equity observations from runs using the pinned
historical policy. The gross realized-loss rule blocked later entries in the
session where it fired. This screen does not replay the entries that a
session-net rule would have allowed, so it cannot establish the resulting
counterfactual equity path, policy value, or daily-loss compliance under a new
policy. It also does not independently reconstruct mark-to-market from every
tick or prove that no unrecorded intrabar excursion occurred. The 2026 period
remains exposed exploratory data. These results do not close Stage E accounting
or lifecycle parity.

Machine reports are embedded in `a4a_training.json`, `a4b_training.json`,
`a4a_testing.json`, and `a4b_testing.json` under
`observed_session_equity_risk_screen`. The reusable audit is
`scripts/research/analysis/evaluation/audit_recorded_equity_series.py`.
