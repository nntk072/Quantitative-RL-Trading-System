# Shared data ABI, version 1

Work package: SHARED-DATA-ABI (`planning/native_modernization/ARCHITECTURE_MODERNIZATION_PLAN.md`, section 3).
Status and evidence: `planning/native_modernization/ledger_entries/SHARED-DATA-ABI.json`.

This document defines the layouts of the arrays that cross from Python into the native kernels, and
the rules those kernels enforce before they accept an input. Source of truth:

- layouts and refusals: `native/domain/src/abi/` (`layout.rs`, `batches.rs`, `error.rs`);
- Python boundary: `native/python/src/abi.rs`;
- Python producer: `market_data/native_abi.py`, which converts `market_data/arrow_schemas.py` and
  `market_data/event_schemas.py` tables into the arrays below.

The ABI is an in-memory contract between two functions. It is not a file format and has no
serialization in version 1.

## Version and compatibility rule

- `SHARED_DATA_ABI_VERSION = 1` (Rust) equals `qrl_native.shared_data_abi_version()` and
  `market_data.native_abi.SHARED_DATA_ABI_VERSION`. The native tests fail if the two differ.
- A version implements exactly the layouts and rules in this document. Nothing is accepted by
  implication.
- A change requires a new version when it changes any of: column order, dtype, rank, nullability,
  unit, mask polarity, the null/NaN encoding, the set of accepted schema identities, or the set of
  inputs that are accepted (a new refusal or a relaxed refusal).
- Columns are not added as optional extensions inside a version. A new column is a new version.
- A reader refuses any version it does not implement (`require_abi_version`). A producer that
  presents a schema identity the payload does not accept is refused with `AbiVersionError`.
- Python and native change together. The layout and schema parity tests in
  `native/python/tests/test_shared_data_abi.py` and `tests/unit/market_data/test_native_abi.py` fail
  when only one side changes.

## Conventions

| Concern | Rule |
|---|---|
| Timestamps | `int64` nanoseconds since 1970-01-01T00:00:00 UTC. This is the physical value of Arrow `timestamp[ns, tz=UTC]`. Columns carry the `_ns` suffix. |
| Prices | `float64` in quote currency per instrument unit. Ticks are a domain concern and are not converted here. |
| Sizes and volume | `float64`, non-negative, source-reported units. |
| Nullable columns | A value array plus a `<name>_valid` `uint8` array. `1` = present, `0` = missing. Same polarity as an Arrow validity bitmap. |
| Missing value | Stored as NaN. A missing slot holding any other number is refused, so a sentinel zero cannot be read as data. |
| Present value | Must be finite. NaN and +/-infinity are refused at the boundary. |
| Masks | `uint8` with values 0 or 1 only. Any other value is refused. NumPy `bool` arrays are refused (dtype `uint8` is required). |
| Filling | No layer fills, interpolates or defaults a value. The Python adapter writes NaN and `0` into the validity array for an Arrow null; it writes no other value. |
| Memory | Row-major (C order). Native-endian. C-contiguous only: strided views and Fortran-order arrays are refused, not copied. Read-only arrays are accepted. |
| Ownership | The native batch copies the input. No Python object is retained after the call, and later changes to the caller's arrays do not affect the batch. |
| Empty input | A batch with zero rows is refused (`AbiError`), not reported as an empty success. |
| Failure | All-or-nothing. A constructor returns a fully validated batch or the first refusal in shape, value, record order. |

## Schema identities

| Identity | Source | Accepted by |
|---|---|---|
| `market-event.v1` | `SCHEMA_VERSION` in `market_data/arrow_schemas.py` | quote batch, bar batch |
| `market-event.v2` | `BAR_REVISED_SCHEMA_ID` | recognised; refused by every payload. Resolve revisions to a v1 view first. |
| `normalized-event.v1` | `NORMALIZED_EVENT_SCHEMA_ID` | recognised; not a payload in version 1 |
| `feature-row.v1` | `FEATURE_ROW_SCHEMA_ID` | feature-row block |
| `account-state-v1` | `OBSERVATION_SCHEMA_V1` in `decisioning/observations.py` | observation window, width 6 |
| `account-state-v2` | `OBSERVATION_SCHEMA_V2` | observation window, width 28 |

`qrl_native.schema_ids()` returns exactly these six strings. The parity test compares it with the
Python constants. Any other string, including an empty one, is refused with `AbiVersionError`.

## Payload layouts

Wire order is the order below. Python passes one array per name in a mapping. Identity scalars
(instrument, source, feature set, version, content hash, schema) are passed as keyword arguments,
not as columns.

### Quote batch (`QuoteBatch.from_columns`, schema `market-event.v1`)

| # | Column | dtype | rank | nullable | unit |
|---|---|---|---|---|---|
| 1 | `event_time_ns` | int64 | 1 | no | UTC ns |
| 2 | `available_at_ns` | int64 | 1 | no | UTC ns |
| 3 | `source_sequence` | int64 | 1 | no | strictly increasing |
| 4 | `bid` | float64 | 1 | yes (`bid_valid`) | quote currency |
| 5 | `ask` | float64 | 1 | yes (`ask_valid`) | quote currency |
| 6 | `bid_size` | float64 | 1 | yes (`bid_size_valid`) | source units, >= 0 |
| 7 | `ask_size` | float64 | 1 | yes (`ask_size_valid`) | source units, >= 0 |
| 8 | `source_flags` | int32 | 1 | no | opaque bits |

Rules, checked in this order: schema; identities non-empty; shapes and lengths; present prices
strictly positive; present sizes non-negative; if both sides are present, `bid <= ask`;
`available_at_ns >= event_time_ns`; `source_sequence` strictly increasing; `event_time_ns`
non-decreasing.

### Bar batch (`BarBatch.from_columns`, schema `market-event.v1`)

| # | Column | dtype | rank | nullable | unit |
|---|---|---|---|---|---|
| 1 | `event_time_ns` | int64 | 1 | no | bar open, UTC ns |
| 2 | `close_time_ns` | int64 | 1 | no | bar close, UTC ns |
| 3 | `available_at_ns` | int64 | 1 | no | UTC ns |
| 4 | `source_sequence` | int64 | 1 | no | strictly increasing |
| 5 | `open` | float64 | 1 | no | quote currency |
| 6 | `high` | float64 | 1 | no | quote currency |
| 7 | `low` | float64 | 1 | no | quote currency |
| 8 | `close` | float64 | 1 | no | quote currency |
| 9 | `volume` | float64 | 1 | yes (`volume_valid`) | tick volume, >= 0 |

Rules: OHLC finite and strictly positive; `close_time_ns > event_time_ns`;
`available_at_ns >= close_time_ns` (an incomplete bar is refused); `low <= min(open, close) <=
max(open, close) <= high`; `event_time_ns` strictly increasing; `source_sequence` strictly
increasing. `market-event.v2` is refused.

### Feature-row block (`FeatureRowBlock.from_columns`, schema `feature-row.v1`)

Identity scalars: `instrument_id`, `feature_set_id`, `feature_version`, `content_hash` (all
non-empty) and `width` (the manifest feature count, at least 1).

| # | Column | dtype | rank | nullable | unit |
|---|---|---|---|---|---|
| 1 | `event_time_ns` | int64 | 1 | no | decision clock, UTC ns |
| 2 | `available_at_ns` | int64 | 1 | no | UTC ns |
| 3 | `session_eligible` | uint8 | 1 | no | 1 = eligible |
| 4 | `values` | float64 | 2, `(rows, width)` | yes (`values_valid`, same shape) | manifest units, row-major |

Rules: matrix width equals `width`; present values finite; missing slots NaN; `available_at_ns <=
event_time_ns` (a feature may not use information after its decision time); `event_time_ns`
strictly increasing; `session_eligible` is 0 or 1. Session eligibility is a mask. Rows are never
removed by this layer.

### Observation window (`ObservationWindow.from_columns`, schema `account-state-v1` or `-v2`)

| # | Column | dtype | rank | nullable | unit |
|---|---|---|---|---|---|
| 1 | `values` | float32 | 2, `(rows, width)` | no | normalized coordinates |
| 2 | `mask` | uint8 | 1, `(rows,)` | no | 1 = real row, 0 = left padding |

`width` is fixed by the schema: 6 for `account-state-v1`, 28 for `account-state-v2`. Rules: values
finite; mask 0 or 1; padding is a left prefix (`0...0 1...1`); padded rows are exactly zero, the
declared pad value of `decisioning.observations.pad_observation_window`. The entry-state one-hot
extension is not part of version 1 and is refused by width.

## Refusals and Python exceptions

| Category | Python exception | Examples |
|---|---|---|
| dtype, byte order, not a buffer | `TypeError` | `float32` for a float64 column, `>f8`, a Python list, a NumPy `bool` mask |
| unknown or foreign schema, unsupported ABI version | `qrl_native.AbiVersionError` (subclass of `AbiError`) | `market-event.v3`, `market-event.v2` on bars, `require_abi_version(2)` |
| everything else | `qrl_native.AbiError` (subclass of `ValueError`) | non-contiguous, shape or length mismatch, non-finite, sentinel in a missing slot, mask not 0/1, ordering, causality, OHLC bounds, empty batch, missing or unexpected key |

Every message names the column and, where one applies, the row. Refusals never convert or repair
the input. The Python validators in `market_data` report every violation for quarantine, whereas
the native layer reports the first one and rejects the whole batch.

## Python adapter (`market_data/native_abi.py`)

- `quote_inputs(table)`, `bar_inputs(table)`: require the `market-event.v1` schema and one
  instrument and source per table. Nulls become NaN with a validity 0. A null in a non-nullable
  column raises.
- `feature_block_inputs(table, width=n)`: each `values` list must have exactly `n` elements.
  Null elements become NaN with a validity 0.
- The `*_ABI_LAYOUT` tuples repeat the Rust layout. The Arrow-to-ABI name map (`event_time` ->
  `event_time_ns`, and so on) is tested against the Arrow schemas without the native extension.

## Build and test

The native extension is built as the in-tree cdylib, which is the same code the wheel packages:

```bash
cd native && cargo build -p qrl-native --offline
cp ../target/debug/libqrl_native.so ../target/python/qrl_native.cpython-312-x86_64-linux-gnu.so
PYTHONPATH=<worktree>:<worktree>/target/python .venv-x86/bin/python -m pytest native/python/tests
```

The Rust gate is `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`
and `cargo test --workspace`, run from `native/` (the workspace manifest is at the repository root).
The Python-only gate is `pytest tests/unit/market_data/test_native_abi.py`.

## Not in version 1

- Zero-copy sharing (`mmap` or Arrow buffers), a `DatasetView` with fold bounds and fitted-state
  references, and per-node sharing across worker processes. The plan's SHARED-DATA-ABI memory
  measurements and process spawn and fork tests are not done.
- Wiring into `simulation/environment/`. The environment does not read these batches yet.
- The `market-event.v2` revision view, `normalized-event.v1` payloads, action and candidate
  layouts, and the entry-state observation extension.
- Serialization. The layout is in memory only, so a file or wire format needs its own version.
