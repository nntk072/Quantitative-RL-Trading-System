# Monthly entry and exit attribution evidence

This semantic packet defines the evidence scope for the paired monthly
attribution documented in
[`docs/research/entry_and_exit_attribution.md`](../../../docs/research/entry_and_exit_attribution.md).
It preserves selected machine evidence in this concept packet and records the remaining historical source lineage in the external checksum archive
and records its checksums in [`evidence_manifest.json`](evidence_manifest.json).

## Claim and reproduction scope

This is an R2 recomputation of paired-trade aggregates for the selected
single-seed policy comparison over the 2025 training interval. It recomputes
monthly counts, means, medians, PnL sums, bootstrap intervals, and the
March-to-April decomposition. The fixed-entry EMA21 path is a conditional
accounting reference, not a causal intervention or portfolio counterfactual.
It does not replay a policy from checkpoints, rebuild fills from raw ticks, or
use the exposed 2026 period. Both policy arms failed the declared account
survival gate.

## Canonical inputs

The paired-trade CSVs and summary are stored in this subject packet under
semantic filenames. The manifest preserves each original source path and SHA-256,
so the byte-identical migration is auditable without making historical run names
the current evidence interface. The older Markdown report remains in the
external checksum archive and is not concatenated into this packet. The reproduction notebook is
[`docs/reproduce/entry_and_exit_attribution.ipynb`](../../../docs/reproduce/entry_and_exit_attribution.ipynb).
The fixed-entry replay helper lives in its evaluation domain at
[`scripts/research/analysis/evaluation/fixed_entry_exit_shadow.py`](../../../scripts/research/analysis/evaluation/fixed_entry_exit_shadow.py).

The older full report and source files are historical records, not the current
human-facing research index. Their relationship to this concept is explicit in
the manifest and in the subject-named research page.

## Versioned figure

The reproduction notebook generates
[`monthly_entry_exit_attribution.png`](monthly_entry_exit_attribution.png)
from the paired-trade rows and records the notebook and image hashes in the
manifest. The figure shows monthly gross mid-quote and historical net R with
the recorded 95% paired-bootstrap intervals. Those intervals describe the
saved single-seed monthly trade rows; they do not estimate seed-level or
out-of-sample uncertainty.
