# Observations and masks

**Status:** Wave B draft
**Use this when:** You need to understand what reaches a policy, how missing or padded values are marked, or how candidate eligibility is represented.

## Summary and use this when

An observation is the complete set of named arrays supplied at one decision
point. Its meaning comes from the stored schema and mask rules, not from shape
alone. The implementation separates the value from evidence about whether that
value is present or eligible.

- Use this guide when adding an observation branch or changing a window.
- Use it when debugging a padded sequence, a missing feature, or an unavailable
  setup candidate.
- Use the [action schema guide](action-schemas-and-parameterization.md) when
  interpreting policy outputs.

## Key terms

- [Observation schema](../../glossary.md)
- [Action mask](../../glossary.md)
- [Availability time](../../glossary.md)

## Explanation

### The rule

`decisioning.observations.pad_observation_window` returns a fixed-length
float32 sequence and a same-window `seq_mask`. Real rows have mask value 1;
left-padding rows have value 0. If the sequence is longer than the window, only
the latest rows are retained. An empty input becomes an all-zero array with an
all-zero mask.

`simulation.environment.observations.schema.prepare_observation_feature_channels`
sanitizes NaN and infinite feature values to zero. When
`env.feature_validity_channels` is enabled, it appends one finite-value flag
per feature to each row. This feature mask is different from `seq_mask`: it
marks individual cells, while `seq_mask` marks real sequence rows.

The common runtime observation contains `seq`, `seq_mask`, and `account`.
Enabled branches may add MTF sequences with one row mask per timeframe, a
regime vector and validity mask, a trade-setup eligibility mask, candidate
geometry arrays, or a VAE latent vector. Branch presence and schema settings
are driven by the environment configuration and saved with model metadata.

### Why it works this way

A numeric zero can be a valid feature value or a replacement for a non-finite
value. The validity channel preserves that distinction without allowing NaN or
infinity into a policy tensor. Padding is a separate condition: its row did
not exist in the observed window, even though its stored values are also zero.

Higher-timeframe observations use completed, causally available rows. With
`completed_htf_history_enabled=False`, the environment retains the configured
branch shape but zeros its values and row mask. This lets encoders consume a
stable observation structure without treating unavailable history as valid.

Trade-setup policies use `trade_setup_mask` to distinguish eligible catalog
entries from unavailable ones. The no-trade category is always eligible.
Candidate-geometry policies expose a separate `candidate_mask` over market
and limit slots; slot zero is always the no-trade choice. These eligibility
masks are not substitutes for sequence or finite-value masks.

### Failure modes

- Reconstructing coordinate meaning from width can load a checkpoint with a
  different account layout or visibility setting.
- Treating every zero as valid can hide missing feature inputs when validity
  channels are disabled.
- Applying `seq_mask` to feature columns, or a candidate mask to a sequence,
  gives the mask the wrong axis and meaning.
- Reversing mask polarity can make an ineligible setup selectable or suppress
  every valid setup.
- Assuming a timeframe branch is populated when its history flag is disabled
  ignores the recorded zero mask.
- Loading a checkpoint whose observation mask or schema differs from the
  current configuration must fail validation rather than silently reinterpret
  its tensors.

## Worked example

The [observation and masks notebook](examples/observations-and-masks.ipynb)
uses a tiny two-feature array with one missing value. It shows left padding,
row validity, finite-value channels, and named observation and candidate
schemas. The example does not instantiate a market feed or make a policy claim.

```{toctree}
:hidden:

examples/observations-and-masks
```

See the [observation contract reference](../../reference/subjects/observations-and-masks.md)
and the full [observation schema reference](../../reference/observation_schemas.md)
for coordinate tables.

## Tasks

- [Add a feature](../../how-to/add_feature.md) and decide whether a finite-value
  channel is needed for its missingness semantics.
- Use [schema versioning guidance](../../how-to/schema_version_change.md) when
  changing stored observation meaning or shape.
- Use the [observation schema reference](../../reference/observation_schemas.md)
  for current branches and account coordinates.

## Contract

| Item | Contract | Source |
|---|---|---|
| Sequence | Float32 fixed window; latest rows retained and short histories left-padded | `decisioning/observations.py::pad_observation_window` |
| Sequence mask | One for real rows, zero for left-padding rows | `pad_observation_window` |
| Feature validity | Optional per-cell finite-value channel; non-finite values are zero-filled | `simulation/environment/observations/schema.py::prepare_observation_feature_channels` |
| Account branch | Named version and ordered coordinates; optional entry-state one-hot extension | `decisioning/observations.py::build_observation_schema` |
| Checkpoint validation | Saved version, width, coordinates, and visibility must match | `validate_observation_schema` |
| Setup eligibility | `trade_setup_mask`; no-trade ID remains eligible | `decisioning/trade_setup.py::trade_setup_observation_schema` |
| Candidate geometry | `candidate_ids`, `candidate_features`, `candidate_mask`; no-trade slot remains eligible | `candidate_geometry_observation_schema` |
| MTF masks | A per-timeframe mask marks real rows; disabled completed history is zero-masked | `simulation/environment/observations/runtime.py` |
| Configuration | `env.feature_validity_channels`, `env.regime_observation`, `env.trade_setup_actions`, `env.candidate_geometry_actions`, `env.mtf` | `config/base/default.yaml` |

## Verify

- `tests/unit/decisioning/test_observations.py` covers sequence padding,
  mask values, schema validation, and account input validation.
- `tests/unit/models/test_trade_setup_observation_schema.py` checks persisted
  setup-mask schema compatibility and manifest recording.
- `tests/unit/simulation/test_environment/test_trade_setup_observation.py`
  checks time-varying setup eligibility and MTF mask behavior.
- `tests/unit/simulation/test_environment/test_observation_schema.py` checks
  configured observation branches and checkpoint schema behavior.
- Research evidence: no trading-performance result is claimed by this guide.

## Limits and common mistakes

- A mask records validity or eligibility according to its own schema; it does
  not establish that a feature or candidate is predictive.
- Zero replacement is safe only when the consumer receives the relevant
  validity signal or the contract explicitly treats zero as the fallback.
- A row mask cannot represent cell-level missingness; a feature mask cannot
  represent missing timesteps.
- Checkpoint compatibility must include schema metadata and settings, not only
  the tensor dimensions.
- The notebook uses synthetic arrays. It does not validate production data
  quality, policy behavior, or research outcomes.

## Change checklist

When an observation changes, identify the producing runtime, the consumer,
the serialized schema, the mask axis and polarity, and the checkpoint field
that carries the contract. Update all four sides together.

- Keep `seq_mask` length aligned with the configured sequence window.
- Keep feature validity aligned with the post-processed feature columns.
- Keep MTF sequence and mask branches in sync when a timeframe is enabled or
  withheld.
- Keep no-trade eligibility explicit when changing the candidate catalog.
- Update the schema version when coordinate meaning, order, or mask semantics
  change; a width-preserving semantic change still needs a new identity.
- Add both matching and mismatching checkpoint fixtures to schema tests.
- Confirm the manifest records all optional observation branch schemas used
  by the model.

## Review procedure

Review a short example at the beginning of a session, after the observation
window fills, and with at least one non-finite feature. Check each emitted key,
shape, dtype, and mask against the declared branch schema. For MTF, test one
completed row and one unavailable-history setting. For candidate masks, test
no-trade and an ineligible setup at the same timestamp. Then compare the
serialized checkpoint metadata to the resolved runtime schema. Synthetic
checks establish shape and mask mechanics only; feed quality and predictive
value require separate evidence.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `ml_engineer`
