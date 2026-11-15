# Live and paper trading contract

**Status:** draft
**Source of truth:** `live/runtime/contracts.py`; `live/runtime/strategy.py`; `live_trading_rl.py`; `integrations/mt5/risk_configuration.py`; `integrations/mt5/`

## CLI and host

`live_trading_rl.py` takes `--model`, `--config`, `--symbol`,
`--secondary-symbol`, `--once`, and `--interval-minutes`.
The model and config environment defaults are `RL_MODEL_PATH` and
`RL_CONFIG_PATH`. The primary and secondary defaults are `US100` and
`US500` via `RL_SYMBOL` and `RL_SECONDARY_SYMBOL`. RL terminal
initialization reads `LOGIN`, `PASSWORD`, `SERVER`, and optionally
`TERMINAL_PATH`. The distribution declares MetaTrader5 for Windows.

`live_trading.py` and `demo_trading.py` delegate to the MT5 multi-symbol
and demo CLIs respectively. All three support `--once`. All default to
paper mode and recognize trimmed, lowercased `false` as a request for
real-order mode. The two rule-based implementations reject that request.
The shipped RL risk manager fails the RL real-order capability check.

## Model and runtime inputs

| Input | Validation or meaning |
|---|---|
| Model file | Must exist. Entry point loads an SB3 PPO/SAC checkpoint. |
| Saved config | Required. Default location is the model grandparent directory's `config.yaml`. |
| Normalization state | Adjacent `feature_normalization_state.json`, schema `feature-normalization-v1`. |
| Manifest | Adjacent `run_manifest.json`, with object records `config`, `feature_normalization`, and `feature_cache`. |
| Provider metadata | `input_schema_version` must equal the live observation schema version. |
| Market source | `get_symbol() -> str`, `get_data() -> pandas.DataFrame`. |
| Live strategy | `signal() -> tuple[str, LiveSignal]`. Enum values are `buy`, `sell`, `hold`, `none`. |

`resolve_feature_normalization_state` requires the manifest and state to be
JSON objects. It checks config and state SHA-256 digests against file bytes,
checks both normalization schemas, and checks the manifest's normalization
filename. It compares `feature_cache.sha256` with `feature_cache_hash` in
both the manifest's normalization record and the state. All three fields
may be absent or null and still compare equal as `None`.

`load_live_risk_configuration` gets `risk_per_symbol_usd_cap` from
`ftmo.risk_sizing_limit_usd`, falling back to `ftmo.risk_per_trade_limit`
when the first value is absent or null. It returns `None` for that cap
when both values are absent or null.

See the [deployment runbook](../../operations/DEPLOYMENT.md) for operational
procedures and the [observation reference](../observation_schemas.md) for
model input semantics.
