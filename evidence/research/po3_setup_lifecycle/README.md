# PO3 setup lifecycle evidence

This packet projects the configured M1 PO3 producer state into accepted setup-sequence rows and separate same-bar conflict rows.
It is diagnostic implementation evidence. Counts describe the configured producer on the declared local training inputs; they are not ground-truth market events, candidate proposals, policy actions, fills, or trades.
Bar-indexed sweep, reclaim, IFVG-confirmation, and FVG-origin times are exact integers recovered from the M1 index. Higher-timeframe pivot and confirmation timestamps remain source float nanoseconds because their nullable producer columns cannot represent epoch nanoseconds exactly.
The feature tensor and action schema are unchanged.

## Contents

- `setup_lifecycle_ledger.csv`: producer-sequence lifecycle rows.
- `setup_lifecycle_summary.json`: counts by event kind, direction, final phase, and termination.
- `resolved_config.yaml`: fully resolved feature and data configuration.
- `event_ledger.json`: source, configuration, input, and limitation metadata.
- `OUTPUT_SHA256SUMS`: packet file checksums.
- `producer_state_validation/`: current synthetic source and lifecycle test
  results, with exact output and source hashes. These tests verify the state
  transition implementation; they do not turn producer counts into ground-
  truth events or actions.

The producer-state validation passed 29/29 focused cases on the current source,
including reclaim/IFVG transitions, conflict separation, prefix invariance, and
ambiguous-state rejection. See `producer_state_validation/` for the run record.

## Regeneration

`python scripts/research/analysis/features/build_po3_setup_lifecycle_ledger.py --config config/2_po3_ifvg.yaml`
