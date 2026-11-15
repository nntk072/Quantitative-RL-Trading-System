# QA: technical-indicators

- Rechecked: 2026-11-15 at HEAD `c0d982f9`; working tree has unrelated dirty files. This restores the missing report and is not a clean original-baseline build.
- Hub: [`../A_data_features/technical-indicators.md`](../A_data_features/technical-indicators.md), 156 lines; required headings and 150–500 page budget: **PASS**.
- Contract reference: [`../../reference/subjects/technical-indicators.md`](../../reference/subjects/technical-indicators.md) exists. Local links: **PASS**; its QA-report link resolves after this report is created.
- Notebook: [`../A_data_features/examples/technical-indicators.ipynb`](../A_data_features/examples/technical-indicators.ipynb); Tier A CPU, bundled/deterministic input, metadata validation **PASS**, saved output cells 1, saved error outputs 0, re-executed in memory in 2.44s (<60s). Notebook is in `examples/`, so no same-stem Sphinx collision.

## Five source-claim checks

| Claim | Source | Result |
|---|---|---|
| EMA, RSI, MACD, ATR, ADX, Bollinger, and stochastic functions are implemented. | `features/technical/indicators.py` | PASS |
| EMA uses causal EWM and preserves input index. | `features/technical/indicators.py::ema` | PASS |
| MACD returns line, signal, and histogram on input index. | `features/technical/indicators.py::macd` | PASS |
| VWAP requires session_id and obtains weighting from activity_series. | `features/technical/indicators.py::vwap_level` | PASS |
| VWAP cumulative totals group by session; zero activity becomes NaN. | same | PASS |

## Limits

The full documentation site build was not run. No research-performance claim is made.
