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

## Regeneration

`python scripts/research/analysis/features/build_po3_setup_lifecycle_ledger.py --config config/2_po3_ifvg.yaml`
