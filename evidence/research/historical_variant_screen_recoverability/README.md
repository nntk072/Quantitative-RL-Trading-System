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
summaries but no trained checkpoint. A later bounded ZIP-container inventory
found `policy.pth` members in archived P6 viability checkpoints. Those files
belong to `p6_entry_fsm_viability` attempt 1. The frozen pair instead identifies
`replacement18_seed50...` attempt 3. The P6 `ppo_best.zip` and `ppo_final.zip`
files are already among the 50 variant-and-seed candidates hashed in the
selected-pair report; neither matches the frozen digest. They are useful
historical artifacts, but cannot stand in for the selected checkpoints or
restore selected-policy attribution. The broader nested-container inventory is
a recovery lead only and does not expand the bounded hash-search scope. The
[checkpoint-container reconciliation](archived_checkpoint_container_reconciliation.json)
records the inventory and the candidate digests. It explicitly classifies these
P6 files as lineage-distinct from the frozen replacement18 attempt-3 pair.
The reusable inventory tool reads ZIP central directories without extraction;
its current report and script hashes are recorded in the reconciliation. Run it
with:

```bash
.venv/bin/python -m scripts.research.analysis.evidence.inventory_archive_containers \
  --root /scratch/work/nguyenl37 \
  --out /scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/run-21376798/archive_container_inventory.json
```

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

## Archived decision-trace content-prefix search

The [content-prefix report](archive_trace_content_search.json) searched all
577 ZIP archives under `/scratch/work/nguyenl37`, including the preserved
research archive and the agent-plan directory. It inspected 42,934 member
names and read at most 64 KiB from each eligible text member: 5,638
CSV/TSV/JSON/JSONL/YAML/text/log members, 11,138,053 prefix bytes total. It
found zero candidate/action/order trace-field leads and no member-read errors.
Sixteen ZIPs were unreadable: ten small pytest fixture files and six
empty/checkpoint-placeholder files in the MTF benchmark directory.

A 16-byte format probe also covered all 42,902 readable file members. It found
no Parquet (`PAR1`) or SQLite signature. The 1,437 ZIP-container signatures
were 1,434 `.pth` files, one `.vsix`, and two nested `.zip` members. A bounded
follow-up opened all 1,437 ZIP-based members with an 80 MiB per-member limit and
inspected their supported text entries; it found zero trace-header leads. The
same 16 unreadable outer archives remain. The scanner did
not deserialize checkpoint payloads, follow directory symlinks, or inspect
text beyond 64 KiB. Archive members were not extracted or hashed. This narrows
the local recovery lead but is not global absence proof or a historical
policy-linkage result. See the
[nested-container report](nested_archive_trace_search.json).
Reproduce it with:

```bash
.venv/bin/python scripts/research/analysis/evidence/search_archive_trace_contents.py \
  --root /scratch/work/nguyenl37 \
  --out evidence/research/historical_variant_screen_recoverability/archive_trace_content_search.json
```

Reproduce the nested-container follow-up with:

```bash
.venv/bin/python scripts/research/analysis/evidence/search_nested_archive_traces.py \
  --root /scratch/work/nguyenl37 \
  --out evidence/research/historical_variant_screen_recoverability/nested_archive_trace_search.json
```

## Missing run artifact byte search

The [missing artifact archive reconciliation](missing_artifact_archive_reconciliation/README.md)
hashed all 42,902 direct file members (21.7 GB uncompressed) in the 577 current
ZIP archives under the same scratch root against the 132 run artifacts still
marked missing by the provenance report. It found no byte-identical artifact;
16 ZIP files could not be opened. A follow-up hash pass reached one additional
ZIP level: it hashed 177,863 members (14.47 GB uncompressed) from the 1,437
inventoried nested checkpoint/ZIP containers and found no exact matches. The
16 unreadable outer ZIP files and deeper nested containers remain unsearched;
all 132 targets remain unavailable in this bounded evidence. This does not
prove global absence.

The same-basename recovery pass now also covers `/home/nguyenl37`: it traversed
9,417 directories with no walk errors, hashed one candidate file (2,515 bytes),
and found zero exact artifact matches. All 132 remain unresolved. This is a
filename-targeted hash check, not a search of differently named files or a
global absence claim; details are in the child packet's
`home_directory_search_metadata.json`.

## Scratch symlink boundary

The [scratch symlink inventory](scratch_symlink_inventory.json) records 5,817
links under `/scratch/work/nguyenl37` without traversing linked directories.
It details 41 links under the current project, preserved research archive, and
the historical thesis workspace name. Existing targets resolve into the
already-searched project data/output trees or to environment interpreters;
three archived data/cache links point into the absent
`/scratch/work/nguyenl37/Aalto_MS_Thesis` tree. The general cache, environment,
and temporary-directory links are counted by top-level directory, not copied
into the focused path list. This bounds the symlink search; it does not resolve
the missing thesis inputs or establish a global artifact search.

Reproduce it with:

```bash
.venv/bin/python scripts/research/analysis/evidence/inventory_scratch_symlinks.py \
  --root /scratch/work/nguyenl37 \
  --focus-name Quantitative-RL-Trading-System \
  --focus-name Quantitative-RL-Trading-System-research-archive \
  --focus-name Aalto_MS_Thesis \
  --out evidence/research/historical_variant_screen_recoverability/scratch_symlink_inventory.json
```

The `/tmp` and `/var/tmp` searches traversed 62 and 1 directories, hashed six same-basename candidates (10,740 bytes) under `/tmp`, and found no exact matches; all 132 targets remain unresolved.
