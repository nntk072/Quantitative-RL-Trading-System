# Scoped mutation check (BASELINE-AUDIT)

Targets: `trading/account/limits.py` and `trading/risk/sizing.py` at base `f96ffcfd`.
Machine-readable copy: `mutation_check.json` in this folder.

## Method

- One mutant at a time. Each mutant is a text substitution that must match exactly once in the file.
- Test set (per run): the oracle file `tests/unit/trading/test_semantic_oracle_limits_sizing.py`, the other files that import `trading.risk.sizing` (`test_risk.py`, `test_risk_properties.py`, `test_fixed_risk_sizing.py`), the unit and integration tests that reach `limits` through `AccountState` (which imports `trading.account.limits`) or call sizing through the environment, and `tests/architecture/test_public_imports.py`. 23 files in total.
- Command: `python -m pytest -q -p no:cacheprovider --tb=no -rfE -o addopts= <test set>`, run from the worktree with `.venv-x86`. Each run was under 80 s (about 18 to 30 s of pytest time).
- After each run the file was restored with `git checkout -- <file>`. `git status --short` showed no production change at the end.
- Unmutated baseline on the same set: 428 passed, 1 warning, exit 0.
- Killed means at least one test failed under the mutant. Survived means every test in the set passed.

## Results

Totals: 10 mutants, 10 killed, 0 survived, 0 inconclusive.

| Module | ID | Mutant | Result | Tests that killed it (failed count) |
|---|---|---|---|---|
| limits.py | L1 | `canonical_daily_loss`: drop the `max(0, ...)` floor | killed | `test_semantic_oracle_limits_sizing::test_daily_loss_is_zero_when_equity_rose` (1) |
| limits.py | L2 | `canonical_daily_loss`: swap operands (sign flip) | killed | oracle `test_daily_loss_is_start_minus_equity_when_losing`, `test_daily_loss_is_zero_when_equity_rose` (2) |
| limits.py | L3 | `daily_floor`: add the loss limit instead of subtracting | killed | oracle `test_daily_floor_is_start_minus_limit`, `test_remaining_daily_capacity_is_equity_above_the_floor`; plus 30 integration and unit tests (32) |
| limits.py | L4 | `remaining_daily_capacity`: drop the `max(0, ...)` floor | killed | oracle `test_remaining_daily_capacity_is_zero_once_breached` (1) |
| limits.py | L5 | `remaining_account_capacity`: clamp constant 0.0 to 1.0 | killed | oracle `test_remaining_account_capacity_above_floor_and_at_floor`; `test_repeated_payout_backtest` `[eod]` and `[intraday_trailing]` (3) |
| sizing.py | S1 | `stop_loss_risk_usd`: drop `abs()` on stop distance | killed | oracle `test_stop_loss_risk_uses_absolute_stop_distance`; `test_account_transition_parity` and `test_risk_lifecycle_characterization` (9) |
| sizing.py | S2 | `compute_lots`: remove the `max_loss_cap` clamp (`lots = lots`) | killed | oracle `test_loss_cap_limits_fractional_sizing`; `test_risk::test_compute_lots_with_cap` (2) |
| sizing.py | S3 | `compute_lots`: apply the loss cap even when `risk_usd` is given | killed | oracle `test_explicit_risk_usd_is_not_shrunk_by_the_loss_cap`; `test_fixed_risk_sizing` `test_explicit_risk_usd_beats_max_loss_cap`, `test_max_lot_ceiling_is_the_only_remaining_limit` (3) |
| sizing.py | S4 | `compute_lots`: lower clip bound `min_lot` replaced by 0 | killed | oracle `test_tiny_budget_is_clipped_up_to_minimum_lot`; `test_risk_properties::test_wider_stop_never_increases_lots_for_the_same_dollar_risk` (2) |
| sizing.py | S5 | `compute_lots_with_execution_reserve`: lot-step `floor` changed to `ceil` | killed | `test_risk::test_execution_reserved_lots_round_down_to_broker_volume_step`; `test_repeated_payout_backtest` (3 params); `test_fixed_risk_sizing`; `test_strategy_env` (8) |

## Observations

- The hand-calculated oracle file killed 9 of 10 mutants on its own (all except S5). S5 (the lot-step rounding direction) was caught only by existing unit and integration tests.
- Integration tests contributed 18 of the 32 failures under L3 and 2 of the 3 under L5. A unit-only run would kill fewer mutants at the same level of detail, so the integration tier matters for these domains.
- No boundary-only comparison mutant was in the set, so this result says nothing about `<` versus `<=` boundaries (for example the `1e-8` zero-distance guard in `compute_lots`). That is a candidate for the next mutant round.
- Scope limit: ten mutants on two modules, not a measure of full mutation coverage.
- The substitution driver and the raw log live in the agent scratchpad, not in the repository.
