# Historical variant-screen artifact recoverability

This packet preserves report-pack recoverability evidence for a historical 18-variant screen. It supports retrospective finding cards only; it is not a current campaign result, checkpoint claim, or candidate-selection input. The copied report is retained byte-for-byte with its original schema and source paths. The packet manifest records its current semantic location and the original source checksum.

## Frozen selected-pair checkpoint search

The [selected checkpoint report](selected_checkpoint_recoverability.json)
compares the two checkpoint digests recorded by the frozen seed-50 selected
pair with ZIP files in the preserved project archive whose paths include the
exact variant name and seed. It records candidate paths, byte counts, stable
SHA-256 values, and whether each frozen run directory is present. This is a
bounded recovery search; it does not make a whole-archive or scratch-wide
absence claim. The current search hashed 50 matching ZIP files (25 per arm,
1,663,296,245 bytes); neither frozen digest matched, and both recorded source
run directories are absent from the preserved archive. This does not exclude
renamed files or backups elsewhere.

Regenerate the report with:

```bash
python scripts/research/analysis/evidence/audit_selected_checkpoint_recoverability.py
```

The selected-pair freeze and report-only interval have already been inspected.
Recovered files therefore remain historical lineage evidence and cannot
upgrade that interval to untouched confirmation evidence.

The historical report records a 2026-10-18 hash scan of the then-current
`outputs/` tree. The [current workspace availability record](current_workspace_availability.json)
checks the known campaign paths again: the old thesis checkout and its named
main-plan, source, and recovery directories are absent from their recorded
locations. The preserved CPU-buffer probe has a source snapshot and campaign
summaries but no trained checkpoint. The current archive filename inventory
finds other checkpoint archives, but does not rehash them against the historic
expected checkpoint digests. This is a path-availability update, not a new
checkpoint recoverability verdict or a full scratch search.

## Archived decision-trace member search

The [ZIP member search report](archive_trace_member_search.json) records a
filename-only scan over `/scratch/work/nguyenl37` on 2026-11-03. It inspected
577 ZIP paths and 42,934 readable member names, finding no recognized
per-decision, candidate-to-action, or order-attempt/submission/acceptance
ledger names. Sixteen paths were unreadable ZIPs: ten small pytest fixture
files and six zero-byte checkpoint files under the separate MTF benchmark
working directory. Those unreadable files contribute no searchable members.

The scanner reads central directories only: it does not extract members or
hash archive contents. It does not follow directory symlinks and searches
member names, so differently named traces or artifacts reachable only through
unlisted roots may remain. This narrows the recovery search but does not prove
global absence or change the historic checkpoint recoverability verdict.
Reproduce with:

```bash
python scripts/research/analysis/evidence/search_archive_trace_members.py \
  --root /scratch/work/nguyenl37 \
  --out evidence/research/historical_variant_screen_recoverability/archive_trace_member_search.json
```
