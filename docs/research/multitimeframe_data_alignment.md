# Multi-timeframe data alignment

## Contract

Higher-timeframe bars must be available only after their interval closes. Feature
construction aligns completed bars forward to decision rows; it must never
backfill a future bar into earlier observations. Native bars and M1-derived bars
are separate inputs whose timestamp, OHLCV, spread, and missingness semantics
must be checked before using the derived cache in a study.

The local raw files span training and testing roles. The exposed 2026 interval
is report-only and cannot be used for architecture or checkpoint selection.
The raw-data identity manifest records retained CSV hashes, but does not certify
calendar correctness, quote chronology, or feature-cache compatibility.

## Regenerate current-source checks

Run the native timeframe comparison and market-data quality profiler on an
approved CPU allocation. These commands create fresh outputs; prior audit outputs are not part of the current evidence set.

```bash
.venv-x86/bin/python scripts/research/analysis/market_data/compare_configured_timeframe_bars.py \
  --out outputs/market_data_quality/configured_timeframe_parity.json

.venv-x86/bin/python scripts/research/analysis/market_data/scan_local_market_data_quality.py \
  --campaign path/to/current-campaign-manifest.json \
  --chunksize 500000 \
  --out outputs/market_data_quality/local_market_data_quality.json
```

The comparison reports timestamp and field differences without claiming which
source aggregation is authoritative. The profiler records source-wall-clock
quality counts; it does not infer missing sessions from timestamp gaps. Keep each report with its input hashes and declared study identity.

See [time and validation concepts](../concepts/data_time_and_validation.md) and
the [research validation protocol](validation_protocol.md).
