# Ticks and resampling

**Status:** Wave A draft
**Use this when:** A procedure needs real bid/ask quotes, or you need to derive
higher-timeframe bars from the one-minute market-data spine.

## Summary and use this when

Tick rows represent quote observations. Resampled bars summarize source bars
into larger intervals. These data forms answer different questions: a candle
does not contain the quote path needed to establish whether an order was
executable between bar boundaries.

- Use ticks for quote-time execution and fill availability checks.
- Use resampling to build a higher-timeframe OHLC view from M1 bars.
- Use the [execution guide](../../reference/risk_and_execution.md)
  for fill and latency semantics.

## Key terms

- [Quote](../../glossary.md)
- [Availability time](../../glossary.md)
- [M1 / M3 / M5](../../glossary.md)

## Explanation

### The rule

`market_data/loading/ticks.py::TickBook.quote_at` selects the first quote at or
after the query timestamp. It returns no stale quote after the last observed
tick. Execution callers must preserve this unavailable state rather than
silently substituting a candle close.

`market_data/transforms/resample.py::resample` aggregates OHLC with first open,
maximum high, minimum low, and last close. Activity columns such as `tickvol`
and volume are summed; `spread` is averaged. Bins are left-labeled and
left-closed.

### Why it works this way

Quote execution needs the first eligible two-sided quote, not an interpolated
price between observations. Resampling preserves a consistent interval label
and gives a reproducible summary for feature calculations. Availability still
depends on the bar close, which is handled by the timeframe alignment contract.

### Failure modes

- Selecting the last tick before an order time uses information that was not
  yet available to that order.
- Carrying a quote beyond the last tick invents executable liquidity.
- Treating candle volume as exchange volume can misstate a CFD feed's activity.
- Resampling empty or malformed input without checking its timezone and column
  schema can produce misleading bins.

## Worked example

This guide's Tier A example builds ten deterministic M1 bars, resamples them to
M5, and asserts the open/high/low/close and summed-activity contract. It uses no
external data and makes no execution-performance claim.

The executable resampling example is linked from the subject area index.

```{toctree}
:hidden:

examples/ticks-and-resampling
```

See the [contract reference](../../reference/subjects/ticks-and-resampling.md) for a compact input and output summary.

## Tasks

- [Prepare market data](../../how-to/prepare_market_data.md) before constructing
  bars or quote caches.
- For quote execution, use the [tick execution notebook](../../learn/tutorials/advanced/tick_execution.ipynb)
  and the execution subject guide.
- For a resampling example, run the notebook embedded below.

## Contract

| Item | Contract | Source |
|---|---|---|
| Tick timestamp | Raw date/time strings are localized to the supplied broker timezone during TickBook construction | `market_data/loading/ticks.py::build_tick_book` |
| Quote sides | Positive bid and ask; crossed pairs are rejected by TickBook build logic | `market_data/loading/ticks.py::build_tick_book` |
| Quote lookup | First tick at or after the requested timestamp; no stale value after end | `market_data/loading/ticks.py::TickBook` |
| M1 passthrough | `resample(m1, "M1")` returns a copy | `market_data/transforms/resample.py` |
| OHLC aggregate | First, max, min, last within each interval | `market_data/transforms/resample.py` |
| Activity aggregate | Sum volume/tick activity; mean spread | `market_data/transforms/resample.py` |

Supported timeframe identifiers are defined by `_TF_TO_RULE` in
`market_data/transforms/resample.py`. The resampler expects a time-indexed M1
frame from the bar loader.

## Verify

- `tests/unit/market_data/test_ticks.py` checks source order, quote lookup,
  cache identity, and unavailable quotes.
- `tests/unit/features/test_htf_alignment.py` checks completed-bar alignment
  after resampling.
- The notebook assertions check the aggregate values on a small fixture.
- Research evidence: no claim about fill quality or tick-feed completeness is
  made here.

Independent QA: [five source-claim checks](../qa/ticks-and-resampling.md).

## Limits and common mistakes

- Tick availability does not establish the quality or completeness of the
  source feed.
- A resampled candle loses the intra-bar sequence of quotes.
- `tickvol` is a source activity count, not necessarily exchange-traded volume.
- This data guide does not define order latency, limit persistence, or slippage;
  those belong to execution contracts.

## Change checklist

When changing quote ingestion or resampling, follow the same timestamp and
availability contract through the consumer. A derived candle cannot recover the
quote path that occurred inside its interval.

- Validate bid and ask ordering and reject crossed or nonpositive quote pairs
  before constructing a lookup book.
- Query at the intended event time and preserve the no-quote result when the
  requested time is beyond available source data.
- Test the first and last quote boundaries, not only a query between two ticks.
- Check every supported timeframe against `_TF_TO_RULE` before adding a new
  identifier to a public caller.
- Verify first/max/min/last OHLC aggregation, summed activity, mean spread,
  left labels, and empty-bin removal with a compact fixture.
- Align resampled bars only after considering when the complete candle becomes
  available to the decision row.

Tick and bar sources have separate cache identities. A change to either source
must invalidate the corresponding derived inputs.

## Review procedure

Use a short fixture that includes two-sided quotes before and after a requested
time, a query before the first quote, and a query after the last quote. Verify
the chosen quote timestamp as well as its price. For resampling, hand-calculate
one full interval and one partial interval; inspect the output labels and every
aggregated column. When resampling feeds higher-timeframe features, then test
the separate alignment step at the candle close boundary. This review catches
aggregation mistakes without pretending that synthetic quotes demonstrate fill
quality on a live broker feed.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`

Record the input and output timezone alongside comparisons so label shifts are
not mistaken for price changes.
