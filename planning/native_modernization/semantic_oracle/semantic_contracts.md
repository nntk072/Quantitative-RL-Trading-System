# SEMANTIC-ORACLE contracts (fixture version 1.0.0)

Work package: SEMANTIC-ORACLE (OFFLINE gate). Branch `feat/semantic-oracle`, base `origin/main-native` (a3b3e442).
Companion files:

- Fixtures (frozen expected values, hand-calculated): `planning/native_modernization/semantic_oracle/fixtures/semantic_oracle_fixtures.v1.json`
- Digest and version of the fixture file: `planning/native_modernization/semantic_oracle/fixtures/MANIFEST.json`
- Command outputs and exit codes: `planning/native_modernization/semantic_oracle/parity_report.md`

This document is the contract the oracle tests enforce. It does not change any source semantics.

## 1. Scope and method

- Expected values were written by hand, with the arithmetic in each case's `hand_calculation` field, before the replay tests were run. No production formula was used to produce an expected value.
- Synthetic tapes only. Captured broker events are not in the tree and were not fabricated. They are not required for offline acceptance.
- Tests replay the fixtures against production code: `tests/unit/trading/test_semantic_oracle_fixture_replay.py`. Hypothesis properties: `tests/unit/trading/test_semantic_oracle_properties.py`. Environment-level metamorphic tests on the real `TradingEnv`: `tests/unit/simulation/test_environment/test_semantic_oracle_env_causality.py`.
- The BASELINE-AUDIT files `tests/unit/trading/test_semantic_oracle_costs.py` and `test_semantic_oracle_limits_sizing.py` are unchanged and remain in the suite.
- No native backend was compared. `qrl_native` is not installed in `.venv-x86`, so backend parity was not run (see section 7).

## 2. Units, dtypes and ordering keys

| Domain | Field | Unit / dtype | Valid range or enum | Notes |
|---|---|---|---|---|
| Quote | `bid`, `ask` | instrument price, float64 | finite, bid > 0, ask >= bid | `_validate_quote` rejects other values before any account mutation |
| Raw bar spread | `spread` (bar column) | MT5 points, float | >= 0 | converted to price with `point_size` (default 0.01) |
| Cost model | `spread_points` | **price units** (naming is misleading, see QF-04) | finite, >= 0 | used as price units when no bar spread exists |
| Cost model | `slippage_points` | price units, float | finite, >= 0 | applied only on protective and tick-quote paths |
| Cost model | `commission_per_lot` | account currency per lot per side | finite, >= 0 | charged on open and on each close |
| Cost model | `point_value`, `point_size` | account currency per price unit per contract unit; price per point | finite, > 0 | |
| Broker | `contract_size`, `margin_pct` | units per lot; fraction | contract > 0 | margin = fill * lots * contract * margin_pct |
| Side | `direction` | int enum | {+1 long, -1 short}; 0 is not a side | see defect C1 |
| Position | `size` | lots, float | > 0 while open | cleared to 0 when residual <= 1e-9 |
| Position | `tp_hit_mask` | int bitmask | bits 0..2 | slot identity used by partial exits |
| Position | `tp{n}_price` | price, float or None | side-consistent after `reorder_remaining_targets` | |
| Account | `balance`, `equity`, `open_pnl`, `daily_loss`, `max_drawdown` | USD, float64 | equity = balance + open_pnl after every valuation | `daily_loss` and `max_drawdown` >= 0 |
| Account | `session_start_equity`, `session_start_balance` | USD | anchors set by `reset_daily` | |
| Guard | `daily_loss_limit_pct`, `max_loss_limit_initial_pct` | fraction in [0, 1] | | limits anchored to initial balance |
| Guard | `breach_reason` | enum | {`trailing_dd`, `max_drawdown`, `daily_loss`, None} | priority in this order |
| Guard | `guardrail_scope` | enum | {`rollout`, None} | any hard loss breach is `rollout` |
| Sizing | `lots` | lots, float | [min_lot 0.01, max_lot 100] or 0 | grid is `lot_step`, floored |
| Sizing | `lot_step` | lots | > 0 | integer count of steps is the exact comparison |
| Targets | `tp_lot_fractions`, `ema_runner_fraction` | fraction | sums and runner in [0, 1] | |
| Timing | bar timestamp | tz-aware datetime, canonical UTC | naive timestamps are rejected by `ftmo_trading_day` | |
| Session | mask | bool per bar | clock-time window, endpoints inclusive | mask only; rows are never removed |
| Reward | `R` reward | dimensionless | `pnl / fixed_risk_usd` | breach replaces the term with -10 |
| Reward | `log growth` reward | dimensionless | `scale * ln(E_after / E_before)` | `E_after <= 0` gives breach penalty |
| RNG | event stream | float64 bits | `SHA-256(seed:event_key)` seeds PCG64 | keyed per logical event |
| Event trace | ordering key | `(bar_index, phase_rank, seq)` | strictly increasing, unique | fixture convention for account traces; env per-step order is in section 3 |

Phase ranks used by account traces: 0 entry or open at the fill quote, 1 protective level (stop or target), 2 mark-to-market or valuation, 3 session boundary.

## 3. Timing and event order (source-verified)

- Decision at bar `t` fills at the open of bar `t + 1` (`episode_runtime.step`, `market_fill_idx = min(step_idx + 1, n - 1)`).
- Step `j` is valued at the bar index `env.step_idx` after the step. Probed values: first valuation bar 61, consecutive thereafter.
- Output `j` depends only on bars with index <= its valuation bar. Bar `v` changes first affect output `v - 1`, through the fill at its open, and output `v`, through valuation. Verified by perturbation at cuts 61, 64, 70 and by the Hypothesis test `test_output_depends_only_on_bars_up_to_its_valuation_index`.
- Per step, in order: market progression and mark-to-market at the current bar close, step constraints with stop and target checks on the current bar (`_check_sl_tp`), action execution at the fill quote, accounting, then observation (`episode_runtime.step`, `step_constraints_runtime`).
- A position opened by a bar-close entry is effective at the bar's end. Its earlier high and low cannot trigger its own stop (`step_constraints_runtime`, `position_has_completed_bar`).
- Stop fills: at the stop level, or at the bar's opening quote if the bar opens through the stop (worse fill). Long: `trigger = min(stop, open)`. Short: `trigger = max(stop, open_ask)`. Adverse slippage is then applied (`trading/execution/quotes.py`). Verified by QF-14..QF-18.
- Ambiguous bars: when both stop and target sit inside one bar and no tick resolves them, the stop wins (`protective_level_runtime._check_sl_tp` docstring, code order sl before tp). Not covered by an env-level oracle in this package (gap G3).

## 4. Tolerance policy

The table lives in the fixture file (`tolerances`), so it is frozen with the expected values. The replay reads it from there.

| Class | Rule | Applies to |
|---|---|---|
| `exact` | bit or string equality | integers, enums, reason codes, booleans, ISO timestamps, ordering keys, state counters, breach flags, RNG bit streams |
| `price_abs` | abs 1e-9 price units | quotes, fills, stop and target levels. Price magnitude 1e2 to 1e4 gives float64 ulp about 1e-12, so 1e-9 is about 1000 ulp |
| `money_usd_abs` | abs 1e-6 USD | balances, equity, pnl, commission, margin, reserves, floors, capacities. Sums of about 10 operations on balances near 1e4 carry error near 1e-11 |
| `lots_abs` | abs 1e-9 lots | unquantized `compute_lots` output |
| `lot_step_exact` | integer step count exact; residual <= 1e-9 lots | any lot result that is on the broker grid |
| `ratio_abs` | abs 1e-12 | dimensionless account fractions in observations |
| `log_reward_abs` | abs 1e-9 | log-growth reward (scale 100, so relative error about 1e-11) |
| `reward_abs` | abs 1e-12 | R-multiple reward |

Risk decisions (breach or not, trade or no trade, margin accept or refuse, lot count) are exact. Floats are compared only in the unit and dtype stated above. Tolerances were fixed before the first replay run and are not tuned to pass a case.

## 5. Disagreements between Python and hand-calculated oracle

Classification uses the four categories from the plan: source defect, oracle defect, documented alternative semantics, backend defect. Status is what the repository contains now. No source file was changed in this package.

| ID | Location | Fixture | Observed | Oracle (hand) | Classification | Status and owner decision |
|---|---|---|---|---|---|---|
| C1 | `trading/execution/costs.py` `CostModel.fill_price` | QF-07 | direction 0 returns bid 99.5 | ValueError | **source defect**: fail-open on an invalid side, against the docstring and INV-OPS | strict xfail. Owner decision: raise for any direction other than +1 or -1. Duplicates `test_semantic_oracle_costs.py::test_invalid_fill_direction_is_rejected_adverse` |
| C2 | `CostModel.fill_price` vs `CostModel.total_cost` docstring | QF-08 | slippage 0.5 long returns ask 100.5 | 101.0 (docstring intent) | **source defect or docstring defect** (not yet decided which). `slippage_points` is applied only on protective and tick paths | strict xfail. Owner decision: apply slippage in `fill_price`, or correct the docstring. Duplicates the costs test xfail |
| C3 | `trading/positions/multi_tp.py` `target_close_size` | TG-05 | 0.01-lot position, leg share 0.003 rounds to 0.0, returns 0.01 (whole position) | close strictly below 0.01 | **source defect**: a rounded-to-zero leg becomes a full exit at TP1 | strict xfail. Owner decision: leg rounds to zero means no exit, or minimum one lot step. Reproducer: `target_close_size(Position(direction=1,size=0.01,entry_price=100,margin_used=0,initial_size=0.01,tp_initial_size=0.01,tp1_price=101,tp2_price=102,tp_lot_fractions=(0.3,0.7)),1,is_final=False)` returns 0.01 |
| C4 | `trading/execution/broker.py` `Broker.open_position` | AC-A2 | after an open with 2.0 commission, balance 9998 but equity 10000 (identity broken) until the next mark-to-market | equity 9998 | **source defect, latent** at the broker API boundary. The env compensates: `entry_execution_runtime` calls `mark_to_market` right after every open (line 172), so env traces are not affected | strict xfail. Owner decision: call `update_equity` inside `open_position`. Not changed here because it alters an API that other callers rely on |
| SZ-14 | `trading/risk/sizing.py` `compute_lots_with_execution_reserve` | SZ-14 | budget 2.9, stop 10: returns 0.28 | 0.29 | **documented alternative semantics** (floor without epsilon, deliberately chosen in the source comment), with an **undocumented** one-step under-size at exact lot multiples because `0.29 / 0.01 = 28.999999999999996` in float64. Conservative; not a risk breach | strict xfail. Owner decision: document the choice, or use a decimal-safe floor (`round` to 12 significant digits before `floor`), which would not reopen the 0.8999999999 case the comment protects |
| SZ-08 | `trading/risk/sizing.py` `compute_lots` | SZ-08 | risk fraction 0 returns min_lot 0.01 | not a hand oracle; documented clip | **documented alternative semantics** (docstring: clipped to [min_lot, max_lot]). Risk concern: a zero budget still trades minimum size. The execution-reserve sizer returns 0 for the same budget | characterization, passes. Owner review recommended |
| TG-06 | `trading/positions/multi_tp.py` `target_close_size` | TG-06 | leg 0.135 rounds to 0.14 | a floor policy gives 0.13 | **source defect candidate: undeclared rounding policy** (round-half-even here, floor in the sizer) | characterization, passes. Owner decision on policy |
| QF-04 | `CostModel.bar_quote`, `exit_side_bar_range`, `protective_level_fill_quote` | QF-04 | `spread_points` used as **price units** (0.6 = 60 points) | field name says points | **documented alternative semantics** (units naming) | characterization, passes. Recommend renaming or documenting |
| RN-04 | `market_data/loading/ticks.py` `event_keyed_execution_rng` | RN-04 | three draws frozen | not hand-calculable (SHA-256) | **characterization only** (no hand oracle possible). Bit-exact golden for fixture version 1.0.0 | passes; any change needs a new fixture version |
| SS-01 | `market_data/transforms/sessions.py` `ny_session_mask` | SS-01 | 16:30 and 23:00 both in window | owner to confirm | **characterization** of inclusive endpoints | passes; owner to confirm convention |
| E1 (env) | `TradingEnv` at data end | `test_data_end_observation_differs_from_in_episode_observation` | observation returned at truncation is not the in-episode observation at the same valuation bar (verified for an 80-bar tape) | no hand oracle; learner contract | **documented alternative semantics, open**: a learner must not bootstrap a truncated transition as a normal next state | characterization, passes. Owner decision: LEARNER-CONTRACT truncation masking |

No oracle defect was found. Every oracle expectation that disagreed with the source was re-checked by hand and is kept as written.

### Mutation evidence for the oracle

Eight single-point source mutants were injected one at a time and then restored (`git` showed no source diff afterwards). Results are in `parity_report.md` section 4. Seven were killed by the oracle. M8 (direction 0 maps to ask) survived. It is equivalent on valid sides (+1, -1) and differs only on the invalid side, which is the open defect C1. The strict xfail does not count as a kill, so M8 is recorded as surviving on that branch.

## 6. Coverage matrix (what the oracle covers now)

| Domain (plan list) | Positive | Adverse or boundary | Where | Status |
|---|---|---|---|---|
| timing (UTC, Prague day, DST) | TM-01..04 | TM-05 naive timestamp; zone-invariance property | fixture + properties | covered |
| bid/ask | QF-01, QF-02, QF-05, QF-06 | QF-03 zero spread; quote invariants | fixture + properties | covered |
| spread | QF-01, QF-04 | QF-03, QF-27 | fixture | covered (units caveat) |
| fees | QF-09 | QF-10, QF-11; commission partition AC-C, AC-C2 | fixture + scenario | covered |
| slippage | QF-12, QF-13, QF-19..22, QF-24 | QF-23 negative slippage; C2 | fixture + properties | covered, C2 open |
| lot and tick rounding | SZ-02, SZ-03, SZ-09, SZ-10, TG-01 | SZ-11, SZ-12, SZ-13, SZ-14 (open item), TG-03 | fixture + properties (risk parity, lot grid) | covered, one open item |
| partial fill | TG-01, TG-02, TG-04, AC-B | TG-03, TG-05 (C3); partition properties | fixture + properties | covered, C3 open |
| pending, cancel, replace | none | none | none | **gap G1** |
| no-trade | env test `test_no_trade_action_keeps_flat_account_and_zero_reward` | | env | covered at env level only |
| equity and margin | AC-A, AC-D, AC-D2 | AC-D refusal; invalid quotes not yet in fixture | fixture | covered |
| daily reset | AC-A reset, AC-E | AC-F boundary; daily-floor property | fixture + properties | covered |
| breach latch | AC-E stateless guard, AC-F priorities | latch persistence in env | fixture | **partial: stateless guard only (gap G4)** |
| gap bars | QF-14, QF-16 | QF-15, QF-17 (gap through stop) | fixture | covered (pure function) |
| ambiguous bars (both levels in one bar) | none at env level | none | none | **gap G3** |
| session mask | SS-01, SS-02 | window wrap and date-shift property | fixture + properties | covered |
| candidate mask and geometry | none | none | none | **gap G2** (`candidate_geometry_observation.py` not exercised) |
| next observation | valuation-index test, prefix invariance | unused-field and future-append tests; E1 characterization | env tests | covered |
| reward components | RW-01, RW-02, RW-05 | RW-03, RW-04, RW-06, RW-07; telescoping property | fixture + properties | covered |
| terminal and truncation | data-end truncation, not terminated | E1 | env tests | partial: truncation covered; episode breach termination not covered at env level |
| RNG | RN-01..03 | RN-02, RN-03 distinct streams; order-independence property | fixture + properties | covered |

Acceptance items in section 3 that remain open are G1 to G4 above, the ambiguous-bar env oracle (G3) and the native backend comparison (section 7).

## 7. Gaps and non-claims

- G1 pending, cancel and replace: the environment has limit-entry orders with expiry and cancel events (`episode_runtime.py`, `order_cancel` with reasons such as `session_end_before_limit_fill`). They are not reachable through pure functions. An env scenario is required.
- G2 candidate mask and geometry: `simulation/environment/candidate_geometry_observation.py` is not exercised here. Existing `test_candidate_geometry_observation.py` covers part of it.
- G3 ambiguous bars at env level: the stop-wins rule is documented but not driven through `TradingEnv`.
- G4 breach latch persistence: the stateless guard is covered. Persistence (`breach_log`, `session_blocked`) across later sessions is not.
- Backend parity: `native/domain` (Rust) has limits and position kernels with Python parity tests (`native/python/tests/test_limits_parity.py`), but `qrl_native` is not built or installed in `.venv-x86`. No backend result is claimed. Recorded as "not run".
- Feature causality (`CAUSAL-FEATURE-GRAPH`) is out of scope. Env tests hold features fixed.
- No claim about profitability, performance or research evidence.

## 8. Golden update policy

- Fixture values are never edited in place. Any change bumps `fixture_version` and `schema_version`, regenerates `MANIFEST.json` in the same change, and records the decision here.
- Strict xfail cases become failures when a source fix makes them pass. That is the intended signal to move the case to positive and bump the version.
- Characterization values (RN-04, SS-01, TG-06, QF-04, SZ-08) are labelled as such and are not hand calculations.
