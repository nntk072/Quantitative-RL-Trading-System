# Saved equity and current local bar identity

The full mark-to-market reconstruction preflight compared the four selected
A4 saved bar-frame fingerprints with the current local M1 frames using the
historical `dataframe_sha256` algorithm recorded in the run manifests. In all
four partitions, row counts, columns, and time bounds match, but the frame
fingerprints do not:

| Partition | Saved run frame SHA-256 | Current local frame SHA-256 |
|---|---|---|
| Training (A4A/A4B share the same saved input) | `6212340f79b3cf7d9b31c60a4717f685bceac55fb4225b51be23f0ec7b380696` | `ddb03dd3494803dfd5fda1dc4edf9f7601301480c5246d119cb1a815dc0819ad` |
| Testing (A4A/A4B share the same saved input) | `2856c00ee00e12d1749e85942119605e22665c67834bdc5b99e258cd90103b13` | `8e394641b9734209e4265e3c978e26b912c61c8e4fd4db236a5f9ff0635bc624` |

The current cache's raw M1 source hash matches its own `native:` source identity
in both splits, and the source config hashes match the saved reanalysis
manifests. Those matches do not repair the saved-versus-current processed-frame
hash difference. The original exact processed bars are not present in the
recorded feature-cache location. Therefore this pass intentionally stopped
before pricing any open positions: matching dates and row counts are not enough
to claim an exact replay of historical mark-to-market equity. Stage E's full
cash/equity/position reconciliation remains open pending recovery of the exact
saved bar frames or another independently verifiable source for them.

Reproduce the identity check with:

```bash
.venv/bin/python scripts/research/analysis/evaluation/audit_saved_equity_bar_identity.py
```

Machine-readable details, including per-partition source paths and hashes, are
in [`saved_equity_bar_identity.json`](saved_equity_bar_identity.json). The
reusable preflight is
[`audit_saved_equity_bar_identity.py`](../../../../scripts/research/analysis/evaluation/audit_saved_equity_bar_identity.py).
