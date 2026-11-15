# QA: feature-causality-and-normalization

- Rechecked: 2026-11-15 at HEAD `c0d982f9`; working tree has unrelated dirty files. This restores the missing report and is not a clean original-baseline build.
- Hub: [`../A_data_features/feature-causality-and-normalization.md`](../A_data_features/feature-causality-and-normalization.md), 159 lines; required headings and 150–500 page budget: **PASS**.
- Contract reference: [`../../reference/subjects/feature-causality-and-normalization.md`](../../reference/subjects/feature-causality-and-normalization.md) exists. Local links: **PASS**; its QA-report link resolves after this report is created.
- Notebook: [`../A_data_features/examples/feature-causality-and-normalization.ipynb`](../A_data_features/examples/feature-causality-and-normalization.ipynb); Tier A CPU, bundled/deterministic input, metadata validation **PASS**, saved output cells 1, saved error outputs 0, re-executed in memory in 2.22s (<60s). Notebook is in `examples/`, so no same-stem Sphinx collision.

## Five source-claim checks

| Claim | Source | Result |
|---|---|---|
| Default completed HTF alignment shifts one row before forward fill. | `market_data/transforms/align.py::align_timeframes` | PASS |
| Explicit availability timestamps can align values to close times. | same | PASS |
| Fit mask requires unique indexes, Boolean dtype, complete coverage, and at least one train row. | `features/pipeline/normalization.py::_aligned_training_mask` | PASS |
| Fitted state is captured as of the last train index. | `features/pipeline/normalization.py::fit_rolling_zscore_state` | PASS |
| Applying fit state validates its schema and columns and reuses stored values. | `features/pipeline/normalization.py::apply_rolling_zscore_state` | PASS |

## Limits

The full documentation site build was not run. No research-performance claim is made.
