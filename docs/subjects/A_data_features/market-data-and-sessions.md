# Market data and sessions

**Status:** Wave A draft
**Use this when:** You need to identify the market rows and broker-time session
labels that enter a feature build, simulator, or evaluation.

## Summary and use this when

The market-data pipeline turns source bars into chronological OHLCV rows with
explicit timestamps, symbol identity, timezone, and provenance. Session labels
describe when a row is eligible for a task; they do not define which rows exist
in the feature dataset.

- Use this guide when loading bar files or checking their timestamp contract.
- Use it when interpreting session labels or configuring evaluation windows.
- Use the ticks guide for quote data and the splits guide for model partitions.

## Key terms

- [Broker timezone](../../glossary.md)
- [Availability time](../../glossary.md)
- [M1 / M3 / M5](../../glossary.md)

## Explanation

### The rule

`market_data/loading/bars.py::load_bars` parses the source timestamp and keeps
the resulting chronological index. The data timezone and timestamp convention
come from the source/configuration contract; a timestamp should not be assumed
to mean a universal exchange close.

`market_data/transforms/sessions.py` assigns session labels in the configured
broker timezone. The default session boundaries in that module are Asia
01:05–09:00, London 09:00–16:30, and New York 16:30–23:00 broker time. Closed
rows can remain between sessions.

### Why it works this way

Features may need bars outside the trade-eligibility window for lookback,
normalization, resampling, or the start of a later session. Removing those bars
changes the timeline and can change the value available at a later timestamp.
`ny_session_mask` is a mask helper; it is not a dataset filter.

Daily bars produced by `market_data/transforms/resample.py` use left-labeled,
left-closed broker-midnight bins. This means a D1 boundary follows the index
timezone rather than an implied UTC midnight or New York close.

### Failure modes

- Mixing UTC timestamps with broker-local timestamps shifts session membership.
- Treating an open-stamped bar as available at its open exposes its final OHLC
  values before the interval has completed.
- Dropping closed-session rows changes the context used by later features.
- Inferring train or test membership from a directory name bypasses the
  configured chronological boundaries.

## Worked example

The [market-data notebook](../../learn/tutorials/01_market_data.ipynb) reads a
small bundled bar sample, checks ordering and OHLC validity, and plots a short
window. It is a software example, not evidence of strategy performance.

```{toctree}
:hidden:

examples/market-data-and-sessions
```

See the [contract reference](../../reference/subjects/market-data-and-sessions.md) for a compact input and output summary.

## Tasks

- [Prepare market data](../../how-to/prepare_market_data.md) and validate the
  resolved symbol, timezone, and chronological range.
- Use the [walk-forward guide](splits-and-walk-forward.md) to define train and
  evaluation partitions.
- Use the [tick guide](ticks-and-resampling.md) when the consumer needs quotes.

## Contract

| Item | Contract | Source |
|---|---|---|
| Bar index | Chronological `DatetimeIndex` parsed from source timestamps | `market_data/loading/bars.py` |
| Bar values | Open, high, low, close, and available source activity fields | `market_data/loading/bars.py` |
| Session label | Broker-time context value; closed rows remain in the dataset | `market_data/transforms/sessions.py` |
| New York eligibility | Boolean mask with configured start and inclusive end | `market_data/transforms/sessions.py::ny_session_mask` |
| Daily resampling | Broker-time midnight, left-labeled and left-closed | `market_data/transforms/resample.py` |
| Configuration | Timezone, timestamp clock, session window, input/output paths | `config/base/default.yaml` |

The [configuration reference](../../reference/configuration.md) lists the
current keys. Exact input columns and cache layouts belong to the generated
reference pages and package guide.

## Verify

- `tests/unit/market_data/test_dataset_source_contract.py` covers bar parsing and source fields.
- `tests/unit/market_data/test_session_schedule.py` covers session masks and
  retained rows.
- `tests/unit/features/test_htf_alignment.py` covers when completed bars become
  available on the decision index.
- Research evidence: no market-performance result is claimed by this guide.

Independent QA: [five source-claim checks](../qa/market-data-and-sessions.md).

## Limits and common mistakes

- Source timezone metadata and feed provenance must be checked separately.
- A successful parse does not prove feed completeness or broker equivalence.
- Session labels describe configured boundaries; they do not establish that
  every broker uses the same trading calendar.
- Keep source files immutable and record source identity before building a
  derived cache.

## Change checklist

Before changing a market-data boundary, review the source timestamp convention,
resolved broker timezone, input schema, and chronological range. Record the
symbol and source identity so a cache can be traced to its raw input.

- Confirm that the loader returns a unique, sorted time index before deriving
  rolling features.
- Check whether timestamps represent bar opens or completed-bar availability;
  downstream alignment must account for that difference.
- Keep closed-session rows in the feature timeline and express eligibility as
  a mask consumed by the trading or evaluation layer.
- Check session labels around configured boundaries in the broker timezone,
  including the inclusive New York end boundary.
- Check that daily resampling follows the index timezone's midnight boundary.
- After changing timezone, session, or source columns, rebuild the cache and
  verify its content identity rather than reusing an old file.

The loader and session helpers describe parsed data semantics. Feed completeness,
calendar exceptions, and broker equivalence require separate evidence.

## Review procedure

Trace one source file through loading, timestamp interpretation, session labeling,
and feature consumption. Compare its first and last source rows with the loaded
index and inspect representative rows at each session transition. When the
configured timezone changes, repeat that boundary inspection after conversion.
Record the settings and source identity alongside any derived cache. A small
row sample can validate parsing mechanics, but it cannot certify a complete
historical feed or a broker's trading calendar.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`

For DST transitions and broker clock changes, check the resolved timezone and
repeat the same boundary procedure; labels are interpreted in that clock.
