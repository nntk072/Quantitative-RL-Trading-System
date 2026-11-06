# Saved A4 bar frames reconstructed from configured raw sources

The first identity preflight compared the saved in-memory bar-frame fingerprints
with current Parquet-loaded frames. Those hashes differed because the cache
round trip does not preserve the exact in-memory pandas hashing identity. The
follow-up rebuilt each saved split directly from the raw M1 file and saved
configuration recorded for the run.

All four reconstructed frames match the original `run_manifest.json` and
`reanalysis_manifest.json` fingerprints exactly: 351,432 training rows with
SHA-256 `6212340f79b3cf7d9b31c60a4717f685bceac55fb4225b51be23f0ec7b380696`, and
279,355 testing rows with SHA-256
`2856c00ee00e12d1749e85942119605e22665c67834bdc5b99e258cd90103b13`. A4A and
A4B record the same frame identity for each partition. The source configs match
their recorded hashes, and each run manifest agrees with its reanalysis
manifest. Each reconstructed raw file's current SHA-256 is recorded in the
machine report.

The exact rebuild applies the run's configured price grid, broker timezone,
cleaning, session labels and IDs, and train/test date split. The saved and
current runtimes both record pandas 2.3.2. The current Parquet frame hash still
differs, so subsequent exact comparisons must use the verified raw-rebuilt
in-memory frames, not the cached frame as deserialized.

This resolves the saved-bar input identity gate and permits a bounded
serialized-ledger mark-to-market reconciliation. It does not itself reconcile
equity, fills, charges, or open positions, and does not establish tick-by-tick
equity or counterfactual policy behavior. Those Stage E checks remain open.

Reproduce with:

```bash
.venv/bin/python scripts/research/analysis/evaluation/audit_saved_equity_bar_identity.py \
  --output evidence/research/simulator_execution_parity/equity_series_reconciliation/source_reconstructed_bar_identity.json
```

The JSON report includes all saved and reconstructed frame fingerprints, raw
input/config/run-manifest hashes, and hashes of the source functions used in
the rebuild. `source_reconstructed_bar_identity.SHA256SUMS` records this report
and the source set.
