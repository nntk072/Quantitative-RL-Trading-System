# Experiment design, controls and ablations contract

**Status:** draft
**Scope:** Conditions for paired return analysis and matched setup baselines.

## Matched returns

Both arms need these provenance fields.

- Data and timeline: `dataset_sha256`, `split_id`, `evaluation_start`, `evaluation_end`.
- Features and action context: `features_sha256`, `reward_sha256`, `environment_sha256`.
- Execution: `costs_sha256`, `execution_sha256`, `initial_capital`.
- Training and replication: `timesteps`, `seed`, `model_settings_sha256`.

Both timestamp indexes must match exactly, with at least two observations,
ordered unique timestamps, and endpoints matching the declared window.
The allowed intervention field is one of `features_sha256`, `reward_sha256`,
`environment_sha256`, `costs_sha256` or `policy_sha256`. When declared it
must contain distinct, non-empty values for both arms, while all other
required fields match. The strict matched-return helper rejects mismatches.

## Setup controls

| Item | Contract |
|---|---|
| Shared replay inputs | Bars, features, tickbook and common evaluation settings. Each arm gets a fresh environment. |
| Period roles | `development`, `exposed_report_only` or `synthetic`. Preserve exposure across replay. |
| Risk | Pass a finite positive absolute ceiling for non-synthetic arms. The setting bounds maximum requested risk. |
| Control semantics | Always-no-trade is the prospective primary comparator, with other eligible random, specified rule or trained arms answering secondary questions. |
| Selection | All required treatment paths must survive before the paired primary result can support selection. |

Sources are `evaluation/metrics/matched_comparison.py`,
`evaluation/rollout/matched_setup_baselines.py` and
`config/research/prospective_research_protocol.yaml`.
`tests/integration/test_matched_comparison.py` directly exercises provenance,
timestamp and intervention checks in `compare_matched_returns`.
See the [subject guide](../../subjects/E_evaluation_research/experiment-design-controls-ablations.md).
