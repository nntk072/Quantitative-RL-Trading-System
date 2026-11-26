# BASELINE-AUDIT defect catalog

Source revision: `a3b3e4422fe7a2c694cf71d837fbb205fbee6f2a` (`origin/main-native` at the time of the audit).
Every defect below was reproduced from source with the x86 interpreter. Run the reproducers with:

```bash
PYTHONPATH=$PWD .venv-x86/bin/python planning/native_modernization/baseline/reproducers/baseline_defect_reproducers.py
```

The script exits 0 only while every defect is observed as recorded here. Per the DECISIONS log (2026-11-26), defects are recorded, not fixed. No source behaviour was changed by this audit.

Severity scale: **High** = changes a feature, cost or evidence value that research or live semantics depend on; **Medium** = fail-open or silent behaviour with a bounded reach; **Low** = latent or hygiene issue with no current caller that changes results; **Review** = a semantic question that needs a contract decision, not a confirmed defect.

| ID | Severity | Location | Status |
|---|---|---|---|
| C1 | Low (latent) | `trading/execution/costs.py:58-76` | Recorded; strict xfail test exists |
| C2 | High (scope to confirm) | `trading/execution/costs.py:43-56, 58-76` | Recorded; strict xfail test exists |
| PREV-DAY-LEVELS | High | `features/technical/structure.py` (`detect_session_levels`) | Recorded; acknowledged in `features/registry.py:68-69` |
| WF-SILENT-EMPTY | Medium | `market_data/splits/walkforward.py:37-88`, `training/runner/walk_forward_validation.py:111-141` | Recorded |
| ARTIFACT-ID-COERCION | Low | `artifacts/identity.py:artifact_id` | Recorded |
| ATOMIC-NEW-FILE-MODE | Low | `artifacts/atomic.py:_atomic_replace` | Recorded |
| JOIN-SAME-STAMP-REVIEW | Review | `market_data/transforms/align.py:join_symbols` | Needs consumer decision-time contract |

## C1: invalid fill direction is priced at the bid

- **Source:** `CostModel.fill_price` returns `ask` only for `direction == 1` and falls through to `bid` for every other value (`else` branch, `trading/execution/costs.py` lines 73-76). The docstring allows only +1 and -1.
- **Reproducer:** `CostModel().fill_price(99.5, 100.5, 0)` returns `99.5` with no exception. Observed value recorded by the reproducer script (`[C1] reproduced=True`).
- **Reach:** `Broker.open_position` rejects directions outside (1, -1) before it calls `fill_price` (`trading/execution/broker.py`, guard near line 185), so the broker open path is protected. `Broker.close_position` passes `-position.direction` without its own guard (line 236). The defect is reachable through direct `CostModel` use and through any future caller.
- **Existing evidence:** `tests/unit/trading/test_semantic_oracle_costs.py::test_invalid_fill_direction_is_rejected_adverse` is a strict xfail that documents the expected raise.
- **Decision:** kept unfixed (DECISIONS, 2026-11-26, cost-model defects C1 and C2).

## C2: `slippage_points` is not applied by `CostModel`

- **Source:** `CostModel.total_cost` documents that "spread/slippage are modeled in fill_price", but `fill_price` uses only the quote side (`trading/execution/costs.py`). `slippage_points` is validated (line 17, 24) and then never read by `fill_price` or `total_cost`.
- **Reproducer:** `CostModel(slippage_points=0.5).fill_price(99.5, 100.5, 1)` returns `100.5`; the documented adverse fill is `101.0`. Observed by the reproducer script (`[C2] reproduced=True`).
- **Reach:** `Broker` bar fills call `CostModel.fill_price` (`broker.py` lines 194 and 236), and `simulation/environment/account_policy_initialization.py:72` builds the broker from the configured cost model. Slippage is applied elsewhere: the tick-quote protective path (`trading/execution/quotes.py:181`), trade accounting (`simulation/environment/trade_accounting_runtime.py:60`) and the tick market-fill override (`evaluation/rollout/trained_policy_rollout.py:704`). This audit did not trace every production bar-fill path end to end, so the reach of C2 on each path is **not confirmed**. Treat severity as High until the SEMANTIC-ORACLE trace is complete.
- **Existing evidence:** `tests/unit/trading/test_semantic_oracle_costs.py::test_nonzero_slippage_worsens_bar_fill_per_docstring_adverse` is a strict xfail.
- **Decision:** kept unfixed (DECISIONS, 2026-11-26).

## PREV-DAY-LEVELS: `prev_day_high` and `prev_day_low` are always null on tz-aware input

- **Source:** `features/technical/structure.py`, `detect_session_levels`. `daily_high` and `daily_low` are grouped by `idx.date` (Python `datetime.date` keys), then `shift(1).reindex(idx)` is applied against a `DatetimeIndex`. Date keys never match timestamp labels, so the reindex is all NaN; the trailing `ffill` cannot recover it.
- **Reproducer:** hourly UTC bars for four days, `detect_session_levels(bars)["prev_day_high"].notna().sum()` is `0` of `96`. Observed by the reproducer script (`[PREV-DAY-LEVELS] reproduced=True`).
- **Why tests pass:** `tests/unit/features/test_session_levels.py::test_prev_day_high_low` uses a tz-naive fixture of 5-minute bars starting at 01:05. Its midnight-stamped rows coincide with the date keys, so 25 of 300 rows are populated (reproducer `[PREV-DAY-FIXTURE-MASK]`). The integration test `tests/integration/test_session_levels_integration.py` asserts only that the columns exist. Neither test uses a timezone-aware index.
- **Reach:** `features/pipeline/feature_matrix_builder.py:659` and `:736`, `features/context/premium_discount.py:371`, `features/registry.py:58-59` (`session_levels`, `prev_day_range`), and trade-setup targets that name `prev_day_high` (`tests/integration/backtest/test_entry_levels.py`). The repository already records this defect in `features/registry.py:68-69` ("values must not change") and it is not fixed here.
- **Severity:** High. Any rule that depends on previous-day levels sees nulls on the production index type.

## WF-SILENT-EMPTY: short series yield zero walk-forward folds without an error

- **Source:** `purged_walk_forward` returns without yielding when `test_region_start < purge + embargo + 1` (`market_data/splits/walkforward.py`, the `min_train` guard). The unit test `tests/unit/market_data/test_walkforward_properties.py::test_invalid_walkforward_inputs_yield_no_folds` asserts this silent result on purpose.
- **Reproducer:** `list(purged_walk_forward(100, n_splits=5, test_size=0.2, purge_bars=60, embargo_bars=20))` returns `[]` with no exception. Observed (`[WF-SILENT-EMPTY] reproduced=True`).
- **Consumer:** `training/runner/walk_forward_validation.py:111-141` builds `expected_fold_ids` from the split list, never checks that it is non-empty, and persists progress with zero expected folds. The runner-level outcome (success with no folds) follows from reading the code; it was not executed end to end in this audit.
- **Severity:** Medium. This is a fail-open path under INV-OPS ("no silent partial success"). Fix options are for the owner; none is applied here.

## ARTIFACT-ID-COERCION: unknown types collide in artifact identity

- **Source:** `artifacts/identity.py:artifact_id` serialises with `json.dumps(..., default=str)`. A NumPy integer is converted with `str()` to `"3"`, which is the same JSON as a string `"3"`.
- **Reproducer:** `artifact_id("probe", {"a": np.int64(3)}).digest == artifact_id("probe", {"a": "3"}).digest` is `True` (observed, `[ARTIFACT-ID-COERCION] reproduced=True`).
- **Reach:** identity is computed from semantic inputs supplied by many callers (`artifacts/__init__.py`, `evaluation/reanalysis/checkpoint_reanalysis.py`, `artifacts/integrity.py`). A caller that passes a numeric type where a string is expected, or the reverse, receives the same identity. No collision is demonstrated in a real artifact here.
- **Severity:** Low (identity can collide under type drift; relevant to INV-EVIDENCE provenance).

## ATOMIC-NEW-FILE-MODE: new files are created 0600

- **Source:** `artifacts/atomic.py:_atomic_replace` creates the temporary file with `tempfile.mkstemp`, which uses mode 0600. The mode is copied only when the destination already exists or `new_file_mode` is given. A new destination with no `new_file_mode` keeps 0600.
- **Reproducer:** `write_json_atomic(new_path, {...})` produces mode `0o600`; the umask default is `0o644` (observed, `[ATOMIC-NEW-FILE-MODE] reproduced=True`).
- **Related observation (not tested):** `_atomic_replace` does not fsync the parent directory after `os.replace`, so a rename is not guaranteed durable after a crash.
- **Severity:** Low. Affects readability of shared-group artifacts; no effect on contents.

## JOIN-SAME-STAMP-REVIEW: cross-symbol join uses the same bar stamp

- **Source:** `market_data/transforms/align.py:join_symbols` applies `merge_asof(direction="backward")` on open-stamped bars with `<=`. The secondary bar that opens at the primary bar's stamp is therefore joined to that primary bar. That secondary bar closes one period later.
- **Contrast:** `align_timeframes` (the default path) shifts higher-timeframe bars by one bar, so a bar becomes visible only after it closes. The two alignment conventions differ.
- **Reproducer:** a primary bar and a secondary bar at the same stamp give `sec_close == 555.0` (`[JOIN-SAME-STAMP-REVIEW] reproduced=True`).
- **Status:** this is causal only if every consumer of the primary row is available at that row's close. The audit did not verify that. It needs a decision-time contract before SEMANTIC-ORACLE uses the join as a reference. It is **not** recorded as a confirmed causality violation.

## Environment and tooling findings (not source defects)

- `.venv-x86/bin/mypy` has the shebang `/scratch/work/nguyenl37/Aalto_MS_Thesis/.venv-x86/bin/python`, which does not exist here, so the launcher exits 127. `.venv-x86/bin/python -m mypy .` runs (see `baseline_check_results.json`). Invocation issue, not a type result.
- `mutmut` (locked at 3.8.1 in `uv.lock`, required by `tools/check mutation-critical`) is not installed in `.venv-x86`. Its wheel is absent from the local uv cache and network is disabled, so the mutation gate could not run. No substitute harness was written.
- `tools/check` resolves its interpreter from the checkout that contains it. In a worktree without `.venv-x86`, set `QRL_PYTHON` explicitly.
- Prior evidence is not bound to a commit: the 8-CPU run (job 21870262) recorded no source SHA. Its `rootdir` was the `main-native` checkout, whose HEAD at run time is not recorded. It was therefore not reused as a result for `a3b3e442`.
- The prior attempt `planning/native_modernization/baseline_audit/` (base `6755417e`, mutation base `f96ffcfd`) is superseded for baseline purposes by `planning/native_modernization/baseline/`. Its mutation results were produced by an ad hoc driver that is not in the repository and are not reproduced here.
