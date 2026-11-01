# Final readiness report

**Snapshot date:** 2026-11-01
**Source:** `3c30030ace717974d32a697395de4e0a32ac943b` (`main` baseline; work is
on `codex/final-research-evidence-release`)
**Verdict:** **BLOCKED — preserve as a negative, exploratory research result;
do not label this snapshot a final thesis or public release.**

## Scientific verdict

On the declared 2025 development interval, both arms of the selected matched
P6 campaign failed its strict zero-breach training risk-survival gate; both
evaluations nevertheless reached the end of the configured data split
(`completed_data_split=true`, `episode_end_reason=data_end`). The generic gate
reason `max_loss_stopped_trading` does not identify the underlying breach type.
The A4A treatment recorded 987 positions and −2.154%, with aggregate ledger
equity ending at $97,845.69 (above the $90,000 floor). Its matched A4B control
recorded 825 positions and −10.056%, with aggregate ledger equity ending at
$89,943.95, $56.05 below that floor. These aggregate endpoints do not override
the per-episode risk-gate failure. Exposed 2026 report-period replays also
failed for both arms and are descriptive only. The evidence does not
demonstrate that any tested policy has an economic edge, nor that the tested
setup-conditioning factor caused the difference.

The first breach event occurred on 2025-03-06 at 20:16 for A4A and 20:32 for
A4B (broker wall clock, UTC+03). Both were `daily_loss` events under
`trading_policy.mode=legacy`. At the pinned campaign source SHA, that mode
accumulated gross negative closed-trade P&L without offsetting winning closes
or using mark-to-market daily equity. The closes through the events sum to
$5,017.66 gross losses / −$3,004.28 net for A4A and $5,399.25 / −$3,389.32
for A4B. Thus the events establish failure of the configured historical
counter, not a net FTMO-style daily-equity breach. A4B had a separate
`max_drawdown` event on 2025-10-28. The stored `fail_time` is the first breach
timestamp, not a terminal episode stop: the rollout separately records
`episode_end_reason=data_end`. The trade trace identifies how the gross-loss
counter tripped but does not explain the policy's stop-out sequence. See the
[risk-gate trace](P6_RISK_GATE_SEMANTICS_AND_BREACH_TRACE.md).

## Gate matrix

| Area | Disposition | Evidence and remaining work |
|---|---|---|
| Source and active-work freeze | Partial pass | Baseline SHA and current branch/worktree captured; the bounded audit job topology is recorded and all audit jobs completed. The local inventory hashes all 140 entries, covering 64 resolved files. A 49-manifest provenance DAG exists. Nested caches, all external outputs, and complete function-to-test relations are not enumerated. |
| P6 artifact lineage | Partial pass | Recovered scratch campaign fingerprint matches the paired decomposition. Ten of ten listed arm artifacts match their recorded hashes. All 38 local data files overlapping the selected P6 inputs match campaign-observed hashes; no checkpoint replay was run. |
| Research result | Negative, bounded | Both full data splits completed and failed the predeclared strict zero-breach gate under legacy gross-losing-close semantics. The March `daily_loss` labels are not FTMO-style net equity breaches; A4B also had an October max-drawdown event. The trace explains the legacy counter crossing, not the policy's stop-out sequence. One seed is not positive viability evidence. The fixed-entry EMA21 decomposition is accounting attribution, not a causal intervention. |
| Data source and quality | Blocked | The local inventory hashes all 140 entries (64 distinct resolved files; 16.33 GB). All 38 selected-campaign data inputs match campaign-observed hashes. Required bid/ask missingness totals 371,390 rows; the selected source snapshot confirms independent per-side forward-fill before retaining quotes. The 329,471 adjacent timestamp ties contain 328,918 changed-quote pairs, 553 pairs with a missing quote, and zero identical-quote pairs. There are 23 uncovered training M1 minutes per instrument. At the user's direction, this uses current local data only; provider/license records are out of scope, and raw data is not included. Full timeframe parity and authoritative schedule remain unresolved. See the [detailed tick diagnostic](current_source_market_input_diagnostic_20261101.json), [data checksum manifest](RAW_DATA_SHA256_MANIFEST.json), and [data provenance dossier](DATA_PROVENANCE_AND_ACCESS.md). |
| Causality and normalization | Partial pass | Current deterministic tests passed for selected indicator prefixes, HTF alignment, and feature behavior. Archived real-data prefix audit source hashes do not match the current source tree. Exhaustive feature-family and two-symbol real-data audits remain open. |
| Setup/action contract | Partial pass | The current scoped suite passed the 12 setup catalog/property checks, 22 observation/environment/integration checks, and nine CPU hybrid-actor checks. One CUDA/ROCm round-trip test was skipped because no accelerator allocation was available. The 108-way real-data opportunity census and price-geometry challenger are not established. |
| Execution, risk, accounting | **Blocked** | Selected tests cover several contracts, but the historical P6 pair used a legacy gross-negative-close daily counter that is not net daily-equity semantics. Both policy modes reset on date-derived `session_id`; equivalence to FTMO 00:00 CE(S)T is unverified. The full lifecycle matrix, explicit versioned daily-loss contract, training/live parity, and independent current real-feed trace remain open. |
| Baselines and model selection | Blocked | The shared continuous baseline evaluator now includes an always-flat reference and labels the default 2026 period as exposed report-only. Classical and supervised implementations exist, but there is no seeded random-eligible policy or fully matched flat/random/rule/supervised/RL registry with common action, cost, risk, independent-seed, and uncertainty semantics. No model is selected. |
| Statistics and untouched validation | Blocked | The entire 2026-01-01 through 2026-10-16 interval is exposed. No untouched confirmatory holdout is available in this evidence package. P6 is one seed; no robust multi-seed claim is supported. |
| Evidence reproducibility | Partial pass | Tracked R2 findings can regenerate bounded tables/figures; recovered P6 external artifacts have a separate hash report. The result registry correctly has no R3/R4 research findings. The release manifest does not claim raw-data R3 or training R4. |
| Software release and docs | Partial pass | Job 21341946 passed full-tree Ruff format/check on 920 files and Mypy on 906 source files. Its scoped suite passed 153 tests, skipped one accelerator-only hybrid-actor test, and emitted two PyTorch nested-tensor warnings. After the final scope edits, strict Sphinx job 21342115 built the latest docs and durably archived 2,587 HTML files with a SHA-256 tree manifest. The release hash maps and evidence audit pass. Full CI and thesis figure/table regeneration remain; no release tag was created. No commit or push was made. |
| Compute and allocation | No training | No training or checkpoint-replay job was launched. The corrected byte audit (job 21339947) verified all 39 hashes. The detailed tick scan (job 21340127) completed in 13:46 on 8 CPUs, with 12 GB requested and 1.95 GiB peak RSS. The preliminary job (21339889) is superseded after an optional-field metric defect. No GH200 utilization claim is made. Historical attempt failures remain immutable evidence. |

## Verification run in this snapshot

The following focused command completed with **54 passed, 2 warnings** using
the checkout's x86 Python module entry point:

```text
.venv-x86/bin/python -m pytest \
  tests/unit/features/test_causal_features.py \
  tests/unit/features/test_htf_alignment.py \
  tests/unit/trading/test_risk_properties.py \
  tests/unit/simulation/test_environment/test_trading_env_golden_traces.py \
  tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py \
  tests/integration/backtest/test_broker_fill_accounting.py \
  tests/integration/backtest/test_broker_quote_parity.py -q
```

The warnings were PyTorch nested-tensor notices in transformer tests. The
installed `pytest` script had a stale shebang pointing to another checkout;
using `.venv-x86/bin/python -m pytest` ran the suite with Python 3.12.14,
PyTorch 2.14.0+cu130, SB3 2.9.0, x86_64, and CUDA unavailable on this host.

A combined 44-test command for setup contracts, properties, hybrid actor,
observation schema, and integration was started. It stopped producing output
after six hybrid actor tests and yielded no pytest summary. The isolated setup
catalog/property command (12 tests) and the separate observation-schema,
simulation, and integration command (22 tests) then completed successfully.
The earlier hybrid-actor attempts were incomplete and are not counted as
current passes. The later CPU-node quality job below supersedes them for the
CPU-available test cases.

The bounded CPU-node verification job 21340375 ran the command listed in
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/verify_release_cpu_20261101.sh`;
it completed with 109 passed and two PyTorch nested-tensor warnings. The
following strict Sphinx build rendered all documentation pages and notebooks,
then failed because the operational plan cross-referenced the readiness README
outside the docs source tree. The path was changed to literal repository text;
the corrected strict build passed on job 21340616.

Additional isolated commands completed successfully: 12 setup catalog/property
tests; 22 observation-schema, environment setup-observation, and setup
integration tests; and two fixture tests for the new current-input audit.
Their exact commands are recorded in [the manifest](RELEASE_MANIFEST.json)
and [function/test index](FUNCTION_TEST_EVIDENCE_INDEX.csv).

The complete local checksum job 21341683 rehashed all 140 inventory entries
(64 distinct resolved files, 16,325,449,095 unique bytes) and confirmed that
all 38 selected P6 data inputs match their campaign-observed hashes. The
inventory-entry byte sum is 32,650,507,987 because symlink aliases appear at
multiple declared paths. Hashes and metadata are recorded in
[`RAW_DATA_SHA256_MANIFEST.json`](RAW_DATA_SHA256_MANIFEST.json); no raw data
was copied into the release.

The final verification job 21341946 rechecked the checksum manifest, then ran
full-tree Ruff format/check and Mypy plus the scoped suite. Ruff passed for 920
files, Mypy passed for 906 source files, and pytest completed with 153 passed,
one skipped, and two warnings in 26.38 seconds.
The skipped test is explicitly accelerator-only (`requires CUDA or ROCm`); no
GPU allocation was available, and no short diagnostic GPU job was created.
Strict Sphinx job 21342115 completed after the final documentation edits with
`build succeeded` and exit code zero. Its 2,587
rendered HTML files are at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/rendered_docs_html_20261101_latest`.
The tree manifest is at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/rendered_docs_html_20261101_latest.manifest.json`
with SHA-256
`3411537e1b3fea142b97b3fce53a5b0dbe34f3a03eab8c28c3ae152bc85f37b9`.

The risk-contract clarification also passed the complete focused policy file:
18 tests passed in
`.venv-x86/bin/python -m pytest tests/unit/trading/test_repeated_payout_policy.py -q`.
Scoped Ruff format/lint and Mypy passed for the new provenance-DAG builder and
the policy test file. The manifest-declared DAG builder indexed all 49
discovered run manifests with zero parse issues (2,848 nodes, 30,391 edges);
it records declared hashes but does not rehash large data/checkpoint files.

## Release decision

This snapshot is suitable as a transparent internal negative-result handoff.
It is not ready for public release or a final thesis evidence claim. At the
user's direction, use only the current local data and do not seek or add an
external export. The underlying provider and license terms were not
investigated, and no raw data is bundled or rights claim made. Investigate the
missing/non-finite bid/ask rows and timestamp ties, and establish the
feed-specific schedule before feature or execution claims are promoted. Do not
train a successor before the active plan's
scientific gates are satisfied. A new matched experiment needs a registered
mechanism, control, factor, acceptance rule, and non-exposed validation plan.
