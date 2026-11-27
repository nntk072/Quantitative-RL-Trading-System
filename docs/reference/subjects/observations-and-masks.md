# Observation and mask contract

This page is a compact subject contract. The canonical coordinate and branch
tables live in the [observation schemas reference](../observation_schemas.md).

## Runtime contract

`decisioning.observations.pad_observation_window` emits a fixed-window float32
array and row mask. Real rows are 1; left-padding rows are 0. Long input keeps
the latest rows; empty input produces zeros and an all-zero mask.

`simulation.environment.observations.schema.prepare_observation_feature_channels`
replaces non-finite values with zero. When `env.feature_validity_channels` is
enabled, it also appends a finite-value channel for each feature. This is a
cell-level signal; it is distinct from the sequence row mask.

The runtime observation assembled by
`simulation.environment.observations.runtime` always includes `seq`,
`seq_mask`, and `account`. Configuration may add `regime` and `regime_mask`,
`trade_setup_mask`, candidate geometry arrays, timeframe sequences and masks,
or a VAE branch. `config/base/default.yaml` is the setting source of truth.

## Eligibility masks

`decisioning.trade_setup.trade_setup_observation_schema` defines the setup
catalog and mask polarity: 1 means eligible, and the no-trade category is
always eligible. Candidate geometry uses its own `candidate_mask`; its first
slot is the no-trade slot. These masks represent action eligibility, not data
availability or predictive confidence.

Timeframe masks describe whether rows are available in a branch. If completed
higher-timeframe history is disabled, the branch remains structurally present
but its values and mask are zeroed by the observation runtime.

## Account schema and compatibility

`decisioning.observations.build_observation_schema` names versioned account
coordinates and visibility settings. The current identifiers include
`account-state-v1`, `account-state-v2`, and
`account-state-repeated-payout`; optional entry state adds four coordinates.
Consumers must compare schema metadata, including ordered coordinate names,
version, width, and visibility. Width equality alone does not establish
compatibility. Legacy metadata is accepted only through the explicit legacy
validation path.

For exact coordinate tables and serialized field shapes, consult the canonical
reference. For implementation behavior, consult `decisioning/observations.py`,
`simulation/environment/observations/schema.py`, and
`simulation/environment/observations/runtime.py`.

## Validation and known limits

Relevant tests include `tests/unit/decisioning/test_observations.py`,
`tests/unit/models/test_trade_setup_observation_schema.py`,
`tests/unit/simulation/test_environment/test_trade_setup_observation.py`, and
`tests/unit/simulation/test_environment/test_observation_schema.py`. They
exercise padding, schema compatibility, and configured mask branches.

The accompanying example uses synthetic arrays. No market-data quality,
policy performance, or trading result has been measured by this contract.
