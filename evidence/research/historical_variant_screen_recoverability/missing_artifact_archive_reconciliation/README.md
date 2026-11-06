# Missing run artifact search in retained local files and ZIP archives

This bounded recovery pass streamed and SHA-256 hashed every readable direct
file member in all `.zip` files found under `/scratch/work/nguyenl37`. It
covered the current 132-item missing set from the provenance byte report and
its declared DAG nodes, without relying on member names.

Results:

- The scan covered 42,902 direct members and 21,671,964,914 uncompressed bytes.
- No byte-identical artifact was found. All 132 targets remain unresolved.
- Sixteen ZIP files could not be indexed (`BadZipFile`). The report status is
  therefore `incomplete_archive_errors`.

The search followed no directory symlinks. Its direct-member pass did not
inspect content inside checkpoint ZIPs. A separate one-level nested-member
hash pass is recorded below. Neither scan proves global absence outside this
root and file set. They do not change the original provenance report or permit
synthesizing any missing historical output. The recovery gate remains open.

A second bounded pass searched ordinary files under the same root. It selected
files whose basenames match one of the 132 missing targets, then compared full
SHA-256 hashes without relying on path identity. It hashed 585 files totaling
3,746,889,603 bytes with zero read errors and zero exact matches. All 132
targets remain unresolved. This adds direct local-file coverage; the 16
unreadable ZIPs, other roots, and differently named ordinary files remain
outside this pass.

Reproduce from the repository root in a compatible Python environment:

```bash
.venv/bin/python scripts/research/analysis/evidence/reconcile_missing_artifacts_from_archives.py \
  --all-members --hash-candidates --max-uncompressed-bytes 32212254720 \
  --workers 8 \
  --output evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/archive_search.json
```

The bounded fixture tests passed 4/4. Commands, input hashes, output hash, and
source/test hashes are recorded in `run_metadata.json` and checksum files.

The ordinary-file pass is reproducible with:

```bash
.venv/bin/python scripts/research/analysis/evidence/reconcile_missing_artifacts_from_filesystem.py \
  --max-candidate-bytes 32212254720 --workers 8 \
  --output evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/local_file_search.json
```

Its two focused tests and the four archive-scanner tests pass together (6/6).
The local-file report, exact inputs, reusable source/tests, and validation log
are recorded in `local_file_search_metadata.json` and `SOURCE_SHA256SUMS`.

A focused same-basename pass also searched `/home/nguyenl37` for the 132
unresolved targets. It traversed 9,417 directories without walk errors, found
one 2,515-byte filename candidate, and hashed it with no exact SHA-256 match.
All 132 targets remain unmatched. This expands the bounded search root; it
does not cover differently named ordinary files or prove global absence.
The report and source/input identities are recorded in
`home_directory_search_metadata.json`.

Reproduce with:

```bash
.venv/bin/python scripts/research/analysis/evidence/reconcile_missing_artifacts_from_filesystem.py \
  --search-root /home/nguyenl37 \
  --max-candidate-bytes 32212254720 --workers 4 \
  --output evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/home_directory_search.json
```

## One-level nested archive member hashes

The [nested archive report](nested_archive_search.json) compares the exact
SHA-256 values of all direct files inside the 1,437 checkpoint/ZIP members
found by the prior nested-container inventory against the same 132 missing
artifact hashes. It hashed 177,863 members totaling 14,469,555,000 uncompressed
bytes in 66.66 seconds, with a 152,776 KiB maximum RSS. There were no exact
matches, no nested-member read errors, and no skipped inventoried containers;
the 16 previously unreadable outer ZIP files remain outside this nested pass.
All 132 targets therefore remain unresolved within the searched nested
members. The report does not deserialize model tensors or recursively open
containers found inside those nested members.

Reproduce from the repository root on a compatible Python environment:

```bash
.venv/bin/python scripts/research/analysis/evidence/reconcile_missing_artifacts_from_nested_archives.py \
  --max-container-bytes 83886080 \
  --max-uncompressed-bytes 107374182400 \
  --output evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/nested_archive_search.json
```

The two focused tests and touched-path Ruff checks pass. The report, source,
test, exact input hashes, and execution profile are recorded in
`nested_archive_search_metadata.json` and the packet checksum files.

A further read-only same-basename search covered `/tmp` and `/var/tmp`. It
traversed 62 and 1 directories, respectively, without walk errors; six candidate
files (10,740 bytes total) were hashed under `/tmp`, and no candidates existed
under `/var/tmp`. Neither root produced an exact match; all 132 targets remain
unresolved. These temporary roots are now covered only for same-basename files,
not differently named files or any locations outside the stated roots. See
`tmp_directory_search.json`, `var_tmp_directory_search.json`, and
`temporary_roots_search_metadata.json`.

Reproduce with:

```bash
.venv/bin/python scripts/research/analysis/evidence/reconcile_missing_artifacts_from_filesystem.py \
  --search-root /tmp --output evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/tmp_directory_search.json
.venv/bin/python scripts/research/analysis/evidence/reconcile_missing_artifacts_from_filesystem.py \
  --search-root /var/tmp --output evidence/research/historical_variant_screen_recoverability/missing_artifact_archive_reconciliation/var_tmp_directory_search.json
```

## Whole-scratch same-basename file search

A read-only extension searched ordinary files under `/scratch` for basenames
matching the 132 missing artifact targets. It hashed 589 files totaling
3,746,898,205 bytes with zero file-read errors and found zero exact SHA-256
matches. All 132 targets remain unmatched. The report is
`scratch_filesystem_search_v2.json`; its command, input/source hashes, output
hash, scheduler context, and bounded claim are in
`scratch_filesystem_search_v2_metadata.json`.

The scan returned status `incomplete_walk_errors` (exit code 2): 3,516
directories elsewhere under `/scratch` were inaccessible to this account. No
walk errors occurred under `/scratch/work/nguyenl37`, the user's research
tree. The inaccessible directories belong to other scratch areas; their
contents are unverified. This does not establish that the artifacts are absent
from all of `/scratch`. The pass also compares only ordinary files with the
same basename; it does not discover differently named files or inspect ZIP
members. It extends the bounded recovery search but does not close Stage A.

The 16 ZIP parse errors from the earlier archive pass were also inspected by
path, byte size, and file signature: ten paths are pytest fixture files of 0,
1, or 10 bytes; the six MTF benchmark checkpoint paths are all zero bytes.
They contain no readable ZIP members. Raw files with matching basenames were
still included in this same-basename hash pass. Nothing was deleted or
rewritten.
