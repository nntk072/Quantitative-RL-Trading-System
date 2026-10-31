# Prepare market data

Use this workflow to turn source bar and tick files into inputs that can be
aligned and consumed by feature construction. Data preparation does not create
features or train a model.

## Before preparing

1. Read the [market-data guide](../modules/market_data.md) and confirm the
   configured symbols, timeframes, timestamp convention, timezone, and split
   boundaries.
2. Keep source files immutable. Record their identity and location outside the
   generated cache directory.
3. Check that the source includes the required timestamp and OHLC columns; tick
   execution also requires usable bid/ask quote fields.

## Prepare and inspect

Use the canonical market-data command. The former `thesis-data` name remains a
deprecated compatibility alias.

```bash
uv run qrl-data prepare --help
uv run qrl-data prepare
uv run qrl-data discover --help
```

`prepare` follows the configured input and output paths. Use `discover` to
inspect the repository's supported data discovery options before changing
paths. Do not point preparation at a live cache directory unless the command's
resolved output and overwrite behavior are understood.

## Validate the result

Confirm the prepared outputs cover the intended chronological range, retain
short sessions and real timeline gaps, contain no duplicate or out-of-order
timestamps, and preserve the expected symbol/timeframe identity. Confirm the
training and evaluation boundaries from resolved configuration rather than
inferring them from folder names. A successful conversion does not validate
feed provenance, causal feature alignment, or execution realism.

Next, follow [build a feature cache](build_feature_cache.md). See the
[reproducibility guide](../concepts/reproducibility.md) for source and cache
identity requirements.
