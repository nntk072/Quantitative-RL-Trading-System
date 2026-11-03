# Local market-data dictionary

This dictionary describes the local MT5-shaped source files included in the
selected campaign input inventory. It documents field shape and known code
behavior; it does not infer provider semantics, rights, authoritative clocks,
or undocumented units. The audit input roles are `calendar`, `testing`, `training`.

The examples below are **synthetic schema examples**, not copied market rows.
Raw data remains in its existing restricted location and is not bundled here.

## Bar CSV fields

The loader accepts intraday rows with `<DATE>`, `<TIME>`, `<OPEN>`, `<HIGH>`,
`<LOW>`, `<CLOSE>`, `<TICKVOL>`, `<VOL>`, `<SPREAD>`, and daily rows without
`<TIME>`. Date/time are parsed as wall-clock values and later localized using
configuration. Daily rows receive a midnight time in the loader. OHLC values
are source price units for the instrument; exact tick-size interpretation
depends on the configured symbol price grid. `TICKVOL` is an integer source
tick-volume field; `VOL` is an integer source-volume field whose external unit
is not established here. `SPREAD` is the source bar spread field; parser
documentation describes it as price points, but no external provider
definition is asserted.

| Field | Unit / representation | Missingness and interpretation |
|---|---|---|
| `<DATE>` | `YYYY.MM.DD` string | Required; source wall-clock date. |
| `<TIME>` | `HH:MM:SS` string | Present for intraday bars; absent for daily bars. |
| `<OPEN>`, `<HIGH>`, `<LOW>`, `<CLOSE>` | instrument price units | Required finite numeric OHLC; OHLC consistency is checked separately. |
| `<TICKVOL>` | integer source count | Source-defined tick volume; not treated as exchange volume. |
| `<VOL>` | integer source value | Unit/provider meaning not independently assessed. |
| `<SPREAD>` | source spread value | Parser docs say price points; symbol conversion and provider semantics are separate. |

Synthetic intraday example:

```text
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>
2025.01.02	01:05:00	100.0	101.0	99.5	100.5	12	0	2.0
```

## Tick CSV fields

Tick exports contain `<DATE>`, `<TIME>`, `<BID>`, `<ASK>`, `<LAST>`,
`<VOLUME>`, and `<FLAGS>`. Tick time strings include milliseconds. The current
quality scan found `<LAST>` and `<VOLUME>` empty throughout the selected tick
exports. `<FLAGS>` is retained as an opaque source field; no flag meanings are
inferred. The configured TickBook builder reads bid/ask only, treats
non-finite and non-positive sides as missing, carries each side forward
independently, rejects invalid/crossed pairs, and retains source order for tied
timestamps. This behavior is not simultaneous-quote proof or within-tie
chronology.

| Field | Unit / representation | Missingness and interpretation |
|---|---|---|
| `<DATE>` | `YYYY.MM.DD` string | Required; source wall-clock date. |
| `<TIME>` | `HH:MM:SS.fff` string | Millisecond-formatted local wall-clock time. |
| `<BID>`, `<ASK>` | instrument price units | Required for a raw two-sided quote; may be missing/non-finite on individual rows. |
| `<LAST>` | source price value | Empty in selected tick exports; unused by the TickBook builder. |
| `<VOLUME>` | source numeric value | Empty in selected tick exports; unit not assessed and unused by TickBook builder. |
| `<FLAGS>` | opaque source string | Present in the exports; semantics intentionally not decoded. |

Synthetic tick example:

```text
<DATE>	<TIME>	<BID>	<ASK>	<LAST>	<VOLUME>	<FLAGS>
2025.01.02	01:05:00.123	100.0	100.5			6
```

## Configured session schedule

`config/ny_session_schedule.csv` contains `session_date`,
`scheduled_ny_close_broker_time`, and `scheduled_short`. These are configured
schedule fields used by local calculations; the file is not asserted to be an
authoritative venue calendar.

## Source and scope

- Current byte/quality report: [`local_market_data_quality.json`](local_market_data_quality.json)
- Configured timeframe comparison: [`configured_timeframe_parity.json`](configured_timeframe_parity.json)
- Example source paths: `data/testing/US100.cash_202412300105_202610162349.csv`, `data/testing/US100.cash_H1_202412300100_202610162300.csv`, `data/testing/US100.cash_H4_202412300000_202610162000.csv`, `data/testing/US100.cash_M10_202412300100_202610162340.csv`
- Source hashes recorded when generated: `market_data/loading/bars.py` = `47d90773b0db0948bf301759cf877f92ff09f77ca8831c5a104f925177c4b7a6`; `market_data/loading/ticks.py` = `50250798b0db1a8a20e5b006705bff40b40861860e538493c407ae28d6d41f83`; the input profile = `ece6f87483318a41ea91ddb4b84f4f378775321229691c5812008f8116b1c97e`.
- The input profile records 39 manifested files and exact byte hashes. This dictionary contains no raw observations.
