# Known limitations and open gates

## Scope note

The user identified the current files as FTMO Demo data and directed local
analysis using only data already in the checkout. The underlying provider and
license terms were not investigated. No raw input is included in this release,
and no redistribution or data-rights claim is made. This is outside the
requested local-analysis scope.

## Release blockers

1. **Data quality and clock:** the complete local inventory hashes all 140
   entries, covering 64 distinct resolved files and 16.33 GB of unique data;
   all 38 selected P6 data inputs match their observed campaign hashes. The
   current campaign-input audit found
   missing/non-finite required bid/ask values in all four tick files, adjacent
   timestamp ties (328,918 changed-quote pairs, 553 missing-quote pairs, no
   identical-quote pairs), and 23 uncovered training M1 minutes per
   instrument. Per-column missingness is in the detailed tick diagnostic.
   Archived audits are source-hash mismatched. Complete tick/bar quality,
   native/resampled parity, timestamp DST interpretation, within-tie ordering,
   within-minute quote availability, and the authoritative instrument-session
   calendar remain open.
2. **Real-data causality:** selected deterministic prefix and HTF tests pass,
   but the archived real-data prefix audit is not current-source evidence and
   exhaustive active-feature, normalization, two-symbol, and candidate-event
   timing coverage is incomplete.
3. **Execution reconciliation:** focused current-source tests pass, but full
   real-feed trace reconciliation across all order, partial-exit, breach,
   session-close, and checkpoint cases is not complete. The selected P6
   campaign used legacy gross-losing-close daily-loss semantics; this is not
   net daily-equity/FTMO semantics. The March events are therefore code-gate
   failures, not verified FTMO daily-loss breaches. A4B separately breached
   the configured maximum account loss. Both policy modes reset on the
   normalized source-date `session_id`; equivalence to 00:00 CE(S)T remains
   unverified.
4. **Comparative selection:** matched flat, random, rule, supervised, and RL
   baselines with independent seeds and uncertainty are incomplete. There is
   no untouched confirmation period.
5. **Release verification:** full-tree Ruff format/check passed for 920 files
   and Mypy passed for 906 source files on job 21341946. The scoped release
   suite passed 153 tests, skipped one accelerator-only hybrid-actor round-trip
   test, and emitted two PyTorch warnings. Strict Sphinx job 21342115 built the
   latest docs and archived 2,587 HTML files with a SHA-256 tree manifest.
   The release hash maps and evidence audit pass. Full CI and figures/tables
   regeneration remain.
6. **Inventory completeness:** the attempt ledger covers the headline selected
   pair, the 100k screen, and the distinct 20M attempt, not all 49 indexed run
   manifests. The function/test index is a focused executed-test map, not a
   complete AST-to-test coverage graph.

## Research interpretation limits

- The P6 result is one seed, on a development interval; its exposed 2026
  replay cannot become a fresh holdout.
- A4A's aggregate ledger endpoint was above the 2025 hard floor, but its
  per-episode risk-survival gate failed early; the aggregate endpoint is not a
  survival pass.
- The P6 decomposition is descriptive accounting over saved cohorts and does
  not prove that entry or exit rules caused the changes.
- The selected policy's class-conditioned action head is not an explicit
  price-conditioned expected-outcome model.
- No real brokerage fill, market impact, or live profitability conclusion is
  supported.
- The separate 20M scratch attempt has a distinct identity and is not evidence
  for the selected pair.

## Remaining source-specific evidence

Use only the current local data as directed; do not add an external export.
Reconcile current data and feature source hashes, verify the feed-specific
timestamp/session calendar, and independently replay the frozen pair before
any R3 claim. The presence of files or hashes in the scratch manifest does not
substitute for these checks.
