# QA: splits-and-walk-forward

- Rechecked: 2026-11-15 at HEAD `c0d982f9`; working tree has unrelated dirty files. This restores the missing report and is not a clean original-baseline build.
- Hub: [`../A_data_features/splits-and-walk-forward.md`](../A_data_features/splits-and-walk-forward.md), 152 lines; required headings and 150–500 page budget: **PASS**.
- Contract reference: [`../../reference/subjects/splits-and-walk-forward.md`](../../reference/subjects/splits-and-walk-forward.md) exists. Local links: **PASS**; its QA-report link resolves after this report is created.
- Notebook: [`../A_data_features/examples/splits-and-walk-forward.ipynb`](../A_data_features/examples/splits-and-walk-forward.ipynb); Tier A CPU, bundled/deterministic input, metadata validation **PASS**, saved output cells 1, saved error outputs 0, re-executed in memory in 2.38s (<60s). Notebook is in `examples/`, so no same-stem Sphinx collision.

## Five source-claim checks

| Claim | Source | Result |
|---|---|---|
| Defaults are five splits, 20% total test, 60 purge bars, 20 embargo bars. | `market_data/splits/walkforward.py::purged_walk_forward` | PASS |
| Total test budget is divided into contiguous blocks at series end. | same | PASS |
| Effective purge adds the nonnegative label horizon. | same | PASS |
| Train cutoff subtracts embargo and effective purge before test start. | same | PASS |
| Fold features retain causal context through validation end but fit on train indices. | `features/pipeline/walkforward_feature_fitting.py::build_walkforward_fold_features` | PASS |

## Limits

The full documentation site build was not run. No research-performance claim is made.
