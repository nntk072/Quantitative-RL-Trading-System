# QA: cache-identity

- Rechecked: 2026-11-15 at HEAD `c0d982f9`; working tree has unrelated dirty files. This restores the missing report and is not a clean original-baseline build.
- Hub: [`../A_data_features/cache-identity.md`](../A_data_features/cache-identity.md), 156 lines; required headings and 150–500 page budget: **PASS**.
- Contract reference: [`../../reference/subjects/cache-identity.md`](../../reference/subjects/cache-identity.md) exists. Local links: **PASS**; its QA-report link resolves after this report is created.
- Notebook: [`../A_data_features/examples/cache-identity.ipynb`](../A_data_features/examples/cache-identity.ipynb); Tier A CPU, bundled/deterministic input, metadata validation **PASS**, saved output cells 1, saved error outputs 0, re-executed in memory in 2.50s (<60s). Notebook is in `examples/`, so no same-stem Sphinx collision.

## Five source-claim checks

| Claim | Source | Result |
|---|---|---|
| Content digest includes the feature-cache version. | `features/pipeline/feature_cache_identity.py::feature_cache_content_hash` | PASS |
| Digest includes resolved feature settings and relevant timezone/session/cost settings. | same | PASS |
| Primary and secondary indexes and supported OHLCV/activity values affect the digest. | same | PASS |
| Named timeframe frames are hashed with their indexes. | same | PASS |
| Train mask contributes count and bytes; path uses a 16-hex digest. | `feature_cache_content_hash`; `feature_cache_path` | PASS |

## Limits

The full documentation site build was not run. No research-performance claim is made.
