# QA: market-data-and-sessions

- Rechecked: 2026-11-15 at HEAD `c0d982f9`; working tree has unrelated dirty files. This restores the missing report and is not a clean original-baseline build.
- Hub: [`../A_data_features/market-data-and-sessions.md`](../A_data_features/market-data-and-sessions.md), 153 lines; required headings and 150–500 page budget: **PASS**.
- Contract reference: [`../../reference/subjects/market-data-and-sessions.md`](../../reference/subjects/market-data-and-sessions.md) exists. Local links: **PASS**; its QA-report link resolves after this report is created.
- Notebook: [`../A_data_features/examples/market-data-and-sessions.ipynb`](../A_data_features/examples/market-data-and-sessions.ipynb); Tier A CPU, bundled/deterministic input, metadata validation **PASS**, saved output cells 1, saved error outputs 0, re-executed in memory in 2.18s (<60s). Notebook is in `examples/`, so no same-stem Sphinx collision.

## Five source-claim checks

| Claim | Source | Result |
|---|---|---|
| Loader parses and sorts bar timestamps. | `market_data/loading/bars.py::load_bars` | PASS |
| Session labels use broker time and documented default boundaries. | `market_data/transforms/sessions.py` | PASS |
| NY eligibility mask includes both configured endpoints. | `market_data/transforms/sessions.py::ny_session_mask` | PASS |
| Adding session labels retains the original rows. | `market_data/transforms/sessions.py::add_session_labels` | PASS |
| D1 uses left-labeled/left-closed bins in index timezone. | `market_data/transforms/resample.py::resample` | PASS |

## Limits

The full documentation site build was not run. No research-performance claim is made.
