# Git source-commit byte reconciliation

The provenance byte verifier now follows each DAG `uses_source` edge to the
consuming run's recorded `source_commit` and hashes that commit's Git blob for
the declared source path. A source node is promoted only when every linked run
commit contains the declared SHA-256. Partial, mismatching, unlinked, invalid,
or missing blobs remain unresolved.

The current DAG has 17 hash-addressed source nodes needing Git-history checks.
Two nodes now verify at every linked source commit; 15 remain unresolved. The
overall provenance report remains `incomplete`, with 132 run artifacts and four
historical data inputs also unavailable. This narrows two source-byte gaps but
does not close campaign inventory, prove run reproducibility, or establish any
trading result.

`source_commit_verifications.json` preserves per-run commit identities and
actual blob hashes. The canonical complete report is
`../PROVENANCE_BYTE_VERIFICATION.json`. Eight focused tests pass, with scoped
Ruff and `git diff --check`.
