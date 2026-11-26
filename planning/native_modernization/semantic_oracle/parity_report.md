# SEMANTIC-ORACLE parity report (fixture version 2.1.0)

Branch `feat/semantic-oracle`. Base `origin/main-native` at `a3b3e442`. Fixture digest `0e4528dcc87905c40e53342e791a464f05ce18450f79ad2982d2c4b6c7a8c977` (`fixtures/semantic_oracle_fixtures.v2.json`, version 2.1.0, pinned in `fixtures/MANIFEST.json`; 2.0.0 digest `21b68771...` superseded).
Python: `/scratch/work/nguyenl37/Quantitative-RL-Trading-System/.venv-x86/bin/python` (3.12.14, pytest 9.1.1, hypothesis 6.170.14), `PYTHONPATH` set to the worktree, `OMP_NUM_THREADS=2`. No network, no broker, no orders, no Slurm.
Raw logs (git-ignored): `logs/agents/quantitative_trading_engineer/2026-11-26_semantic_oracle/`. The lines below are exact.

## 1. Required checks (exit codes)

Final battery, log `final2_checks.log`:

| # | Command | Exit | Output |
|---|---|---|---|
| 1 | `ruff format --check` on 4 touched source files and 5 test modules | 0 | `9 files already formatted` |
| 2 | `ruff check` on the same 9 files | 0 | `All checks passed!` |
| 3 | `python -m mypy` on the same 9 files | 0 | `Success: no issues found in 9 source files` |
| 4 | `python -m pytest -q -p no:cacheprovider -o addopts= -rxs` on the 5 new or changed oracle modules, `test_semantic_oracle_limits_sizing.py` and `tests/unit/research_tools/test_study_audits.py` | 0 | `160 passed, 2 skipped in 21.38s` |
| 5 | `sha256sum` of the v2 fixture | 0 | `0e4528dcc87905c40e53342e791a464f05ce18450f79ad2982d2c4b6c7a8c977` (equal to `MANIFEST.json`) |

The 2 skips are the open items O2 and O3 (`test_open_env_scenario_is_visible_not_passed`). No xfails remain: C2 is resolved as documented semantics in 2.1.0.

Wider regression (log `regress.log`): `python -m pytest -q -p no:cacheprovider -o addopts= tests/unit/trading tests/unit/simulation` gave `948 passed, 2 skipped, 2 xfailed, 4 warnings in 108.22s`, exit 0 (before C2). Re-run after the C2 docstring and test changes: `950 passed, 2 skipped, 4 warnings in 87.53s`, exit 0 (log `final3_checks.log`).

Study-catalog audit: first failure was the inventory check. It was fixed by registering the new callers and API paths in `config/studies/profiles/{market_data,trading,simulation,decisioning}.yaml`. Final `test_study_audits.py`: `4 passed in 42.88s`, exit 0.

## 2. Source changes in 2.0.0 (each with evidence)

| ID | Change | Test that pins it | Evidence changed |
|---|---|---|---|
| C1 | `CostModel.fill_price` raises `ValueError` for a direction other than +1 or -1 | fixture QF-07 (adverse), `test_invalid_fill_direction_is_rejected_adverse` (xfail marker removed) | `trading/execution/costs.py` |
| C3 | `target_close_size` returns 0.0 (not the whole position) for a zero leg, a runner-clamped leg, or an inactive slot. Three callers consume the slot without a broker close | fixture TG-05 (adverse); `test_zero_target_leg_consumes_slot_and_keeps_position` (env, 0.01 lots, TP1 30 %: position stays at 0.01, `tp1_price` None, `tp_hit_mask` bit 0 set, no trade) | `trading/positions/multi_tp.py`, `simulation/environment/protective_level_runtime.py` (2 sites), `simulation/backtest/protective_management.py` |

The backtest caller (`protective_management.py`) is covered only by the shared `target_close_size` fixture; no runtime test drives it (open item O4).

Behavior changed by C1 and C3, so evaluation evidence that depends on them is not comparable with the pre-2.0.0 identity: a zero-size TP leg no longer exits the whole position, and an invalid side now raises.

## 3. Decisions recorded without a source change

| ID | Decision | Evidence |
|---|---|---|
| C2 | **Resolved as documented semantics (version 2.1.0, owner decision).** `fill_price` selects the quote side and does not apply `slippage_points`. Slippage is applied to the quote on the tick and protective paths before `fill_price`. The `total_cost` docstring was corrected (no behaviour change). QF-08 is pinned at 100.5, and `test_fill_price_does_not_apply_slippage_points_double_count_guard` names the double-count risk. Evidence for the risk: `config/base/default.yaml` `costs.slippage_points: 5.0` reaches the env `CostModel` (`trading_environment_factory.py`), and both quote paths apply it before `CostModel.fill_price`. Source trace, not a numerical run. |
| C4 | Known broker-boundary limit, pinned | `test_known_broker_boundary_limit_open_position_equity_is_refreshed_by_mark`: after `Broker.open_position` with commission 2.0, balance 9998.0, equity 10000.0 (stale), open_pnl 0.0. After `mark_to_market` at bid 100.0 / ask 100.6, equity 9938.0 = balance + open_pnl. The env calls mark after every open (`entry_execution_runtime.py`). |
| SZ-14 | Documented rule pinned: floor in float64, no epsilon | fixture SZ-14 `expect 0.28`; hand value 0.29 is kept in the note. Probe output: `reserve lots 0.29: 0.28` and `0.29/0.01 = 28.999999999999996 floor: 28.0` |
| TG-06, TG-07 | Documented rule pinned: `round(x, 2)`, round-half-even on float64 | TG-06 `0.135 -> 0.14`; TG-07 `0.125 -> 0.12` (exact midpoint goes to the even neighbour) |

## 4. Mutation evidence

The 1.0.0 mutation run is recorded in the parity report of that version (seven of eight killed). M8 was the invalid-direction branch of `fill_price`, which is now fixed (C1). The 2.0.0 mutation re-run was **not performed** in this pass. The mutant set in version 1.0.0 remains in `logs/agents/quantitative_trading_engineer/2026-11-26_semantic_oracle/mutation_check.log`.

## 5. Scenario coverage added in 2.0.0

Env scenarios (`tests/unit/simulation/test_environment/test_semantic_oracle_env_scenarios.py`, replayed from the `env_scenarios` section of the fixture):

- G1 pending limit order: cancel on session change (positive); session change beats an available fill (adverse); fill inside the bar interval at the quote ask 20000.6 (positive); no fill when the quote is after the interval end (adverse). Replace: `not_applicable`, since no replace or amend name exists on `TradingEnv`.
- G3 ambiguous bars, long, SL 99.0, TP 101.0: both levels inside the bar gives stop at 99.0 (positive); TP-only gives target at 101.0 (positive); SL-only gives stop at 99.0 (adverse); no touch keeps the position (adverse).
- G4 breach latch, non-episodic: control with no breach opens a position (positive); `close_trade(-11000)` then 40 entry requests gives zero opens, `breach_log == ['max_drawdown']`, `year_failed` True (adverse). Within session only.
- G2 candidate mask, geometry disabled: only the no-trade slot is eligible (positive); setup ids present but disabled stay masked (adverse).

Open items, each shown as a skip so they are visible:

- O2 enabled candidate-geometry mask (needs a full synthetic env).
- O3 cross-session latch. The 1500-bar tape has its first NY window end at bar 451 and only one step in the second session, so cross-session persistence is not shown.

Probe evidence for G4 (before the test was written): control `opened_at [61]`, `breach_log []`, `year_failed False`; breached `opened_at []`, `breach_log ['max_drawdown']`, `year_failed True`. Two-session probe: breached run sessions `{20093: 390 steps, 20094: 1 step}`, `opens 0`; control `{20093: 17 opens, 20094: 0}`.

Probe evidence for the causality contract (earlier pass): `cut 61 first differing step index 0`, `cut 64 ... 3`, `cut 70 ... 9`.

Test-design hazard recorded earlier: `_make_features` draws depend on tape length, so prefix tests must slice features, not regenerate them.

## 6. Not run, not claimed

- Native backend parity: **skipped, recorded reason**: `qrl_native` is not built or importable in `.venv-x86`. Building it is out of scope for this package. Nothing about backend equivalence is claimed.
- Captured broker events: not in the tree, not required, not used.
- Full repository gates (full-tree ruff, full-tree mypy, `./tools/check unit`, full unit suite): not run. Scope was the touched files, the oracle modules, the trading and simulation directories, and the study audit.
