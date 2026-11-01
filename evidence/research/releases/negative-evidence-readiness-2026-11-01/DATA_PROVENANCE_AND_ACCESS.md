# Data provenance and access

## Data role

The selected pair used training dates 2024-12-30 through 2025-12-31. The
2026-01-01 through 2026-10-16 report interval is exposed exploratory evidence.
The configured market inputs include US100 and US500 bars and bid/ask ticks;
the project also configures M1, M3, M5, M10, M15, M30, H1, H4, and D1 views.
Exact native-versus-derived provenance and byte identity have not been
established for the full configured universe. The bounded audit below covers
only the 39 files named by the selected P6 campaign manifest.

## Source and rights

Historical audit records and the user identify the source as FTMO Demo. The
underlying liquidity provider and license terms were not independently
investigated because the user directed local analysis on current files only.
This release contains no raw market data and makes no rights or redistribution
claim. The existing files remain in their current local locations.

The user directed this work to use only data already present in the checkout
and not to seek or add an external export. This scope does not establish the
underlying provider or license terms, but those external records are not a gate
for local analysis under the user's direction.

## Recovered P6 campaign

Scratch contained the selected pair's run directory, source snapshot, resolved
configs, per-arm provenance, final checkpoints, and train/test trade ledgers.
The campaign fingerprint matches the tracked decomposition; 10/10 listed
per-arm artifacts match recorded hashes, and 39/39 manifest input paths exist.
The current-source audit streamed and SHA-256 checked all 39 files (8,162,529,858
bytes); all 39 match the campaign manifest. This establishes byte identity to
that manifest, not source identity or rights. The separate 20M-step
scratch attempt has a different fingerprint and only seven training positions
per arm; it is not the selected pair and must not be resumed or conflated.

The audit found no timestamp parse failures or adjacent timestamp reversals,
invalid OHLC rows, or non-finite/missing required bar fields. It did find
adjacent timestamp ties in the tick files (237,775 and 27,734 in training;
62,606 and 1,356 in testing for US100 and US500, respectively). These are ties
at the timestamp precision exported and leave within-tie event ordering
unresolved. The detailed scan classifies 0 tied pairs as identical quotes;
328,918 pairs have changed bid/ask values and 553 have at least one missing
quote. All 329,471 ties therefore lack an unambiguous equal-quote explanation.
Rows with at least one non-finite or missing required bid/ask value were
161,302/56,245,046 (US100 training), 129,419/16,784,324 (US500 training),
73,415/78,798,505 (US100 testing), and 7,254/20,462,508 (US500 testing).
There are no rows with both bid and ask missing; the column counts are: US100
training 61,342 bid / 99,960 ask, US500 training 34,954 / 94,465, US100
testing 36,728 / 36,687, and US500 testing 3,523 / 3,731. The scan found no
nonpositive or inverted quotes among parsed values and no adjacent timestamp
reversals. MT5 tick exports also contain blank optional `LAST` and `VOLUME`
columns; the corrected audit counts these separately and does not confuse them
with required bid/ask quality.
Training M1-to-tick overlap is 351,409/351,432 minutes for US100 and
349,950/349,973 for US500 (23 uncovered minutes each). Testing overlap is
279,355/279,355 for US100 and 278,956/278,956 for US500. This is minute-level
overlap only, not evidence of a quote at a specific order-arrival time.
The [machine-readable campaign audit](current_source_market_input_audit.json)
records per-file hashes and core counts; the
[detailed current-source diagnostic](current_source_market_input_diagnostic_20261101.json)
adds per-column missingness and timestamp-tie quote classification. The earlier
[preliminary report](current_source_market_input_audit_preliminary_20261101.json)
is retained but superseded because its first tick-quality metric incorrectly
treated optional blank fields as required.

The tick builder carries bid and ask independently across missing/non-finite
source-side values, then retains finite, positive, non-crossed quote pairs.
Inspection of the selected campaign's source snapshot records
`market_data/loading/ticks.py` SHA-256
`205a9eef9cd8f80df0aa08b8bd59874b5d71bf395d807fef693619077ef24b77`; its
missing-side processing block is byte-identical to the current worktree's
block (current file SHA-256
`518beb9255b3dd48e0e4fe9c54051dcb596505a9b9aba9cd5a33b25d35843ff2`). A
retained row can therefore pair a newly observed side with a value carried
from an earlier source row. This is deterministic parser behavior, but does
not prove that both sides were simultaneously available at that timestamp.
Same-time changed quotes also retain source order, which does not establish
sub-millisecond chronology. These facts constrain execution claims for the
selected run.

## Current-source audit boundary

Previously archived M1/tick and feature-prefix reports are historical: the
recorded source hashes do not match the current source files. Their results
cannot be promoted as current-source gates. The new audit scans the campaign's
training/testing bars and ticks but does not check complete derived-timeframe
parity, classify market closures, or validate all feature inputs. The complete
local-data inventory lists and hashes all 140 entries. Several entries are
aliases to the same resolved files: there are 64 distinct resolved files
totaling 16,325,449,095 bytes; inventory-entry sizes sum to 32,650,507,987
bytes because aliases are counted at each listed path. The checksum manifest
preserves each declared path and its resolved path, and hashes each distinct
target once while checking stable file identity. All 38 local data files
overlapping the selected P6 campaign inputs match the campaign-observed
SHA-256 values. See
[`RAW_DATA_SHA256_MANIFEST.json`](RAW_DATA_SHA256_MANIFEST.json). This proves
local byte identity for the snapshot, not feed provenance, licensing,
timeframe equivalence, or schedule correctness. The preliminary checksum
export is retained as superseded evidence after its alias paths were
canonicalized ambiguously.

## Timestamp and schedule

The current base configuration selects `ftmo_mt5_us_dst`, wall-clock export
timestamps, and `Etc/GMT-3`. These config choices do not independently prove
the source server's actual DST history or the instrument's full holiday,
partial-session, and unscheduled-closure calendar. Archived schedule evidence
does not establish the current feed's authoritative calendar. Keep date-shape
and calendar questions unresolved until checked against source-specific
authoritative evidence.

## Access and reproduction

Restricted data remain in their existing locations and are referenced by the
external campaign manifest. This repository release snapshot contains no raw
market data or checkpoints. Reproduction of the paired-row analysis is
available from the tracked notebook linked in the [result registry](../../../../docs/reproduce/result_registry.md).
Full checkpoint replay and training reproduction are not claimed.
