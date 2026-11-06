# Local tick quote coverage

This packet reconciles the configured training M1 `tickvol` counts with local raw tick-row counts and checks whether every raw row has a usable two-sided quote. It is a local-source consistency audit, not evidence that the export is complete relative to an external venue. `minute_quote_coverage.csv` can be joined to proposal fill and exit intervals; any interval containing an incomplete minute must remain unresolved for negative-touch claims.

The training window is configured in the resolved project config. Input hashes and aggregate reconciliation counts are recorded in `coverage_manifest.json`.
