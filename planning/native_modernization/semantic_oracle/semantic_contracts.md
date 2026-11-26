# SEMANTIC-ORACLE contracts (fixture version 2.2.0)

Work package: SEMANTIC-ORACLE (OFFLINE gate). Branch `feat/semantic-oracle`, base `origin/main-native` (a3b3e442).
Companion files:

- Fixtures (frozen expected values, hand-calculated): `planning/native_modernization/semantic_oracle/fixtures/semantic_oracle_fixtures.v2.json`
- Digest, version and supersession record: `planning/native_modernization/semantic_oracle/fixtures/MANIFEST.json`
- Command outputs and exit codes: `planning/native_modernization/semantic_oracle/parity_report.md`

## 1. Scope, method and versioning

- Expected values were written by hand, with the arithmetic in each case's `hand_calculation` field, before the replay tests were run. Production formulas were not used to produce expected values.
- Version 1.0.0 (digest `d0e3f996...`) was the first freeze. Version 2.0.0 (digest `21b68771...`) recorded fixed source defects C1 and C3 and added env scenarios. Version 2.1.0 (digest `0e4528dc...`) pins the C2 decision (documented semantics, docstring corrected). Version 2.2.0 (current, digest in `MANIFEST.json`) closes O2 and O3 with env scenarios and adds the O4 runtime test; it changes no expected value. Each version's `changes_from_*` block lists the change and the evidence it changed.
- Synthetic tapes only. Captured broker events are not in the tree and were not fabricated. They are not required for offline acceptance.
- Tests: fixture replay `tests/unit/trading/test_semantic_oracle_fixture_replay.py`; Hypothesis properties `tests/unit/trading/test_semantic_oracle_properties.py`; env metamorphic tests `tests/unit/simulation/test_environment/test_semantic_oracle_env_causality.py`; env scenarios (pending orders, ambiguous bars, breach latch, candidate mask, zero target leg) `tests/unit/simulation/test_environment/test_semantic_oracle_env_scenarios.py`.
- Native backend parity: **skipped, with recorded reason**. `qrl_native` is not installed in `.venv-x86`. Building it is out of scope for this package.

## 2. Units, dtypes and ordering keys

| Domain | Field | Unit / dtype | Valid range or enum | Notes |
|---|---|---|---|---|
| Quote | `bid`, `ask` | instrument price, float64 | finite, bid > 0, ask >= bid | `_validate_quote` rejects other values before account mutation |
| Raw bar spread | `spread` (bar column) | MT5 points, float | >= 0 | converted to price with `point_size` (default 0.01) |
| Cost model | `spread_points` | **price units** (name is misleading, QF-04) | finite, >= 0 | used as price units when no bar spread exists |
| Cost model | `slippage_points` | price units, float | finite, >= 0 | applied on protective and tick-quote paths (see C2) |
| Cost model | `commission_per_lot` | account currency per lot per side | finite, >= 0 | charged on open and on each close |
| Cost model | `point_value`, `point_size` | account currency per price unit per contract unit; price per point | finite, > 0 | |
| Broker | `contract_size`, `margin_pct` | units per lot; fraction | contract > 0 | margin = fill * lots * contract * margin_pct |
| Side | `direction` | int enum | {+1 long, -1 short}; anything else raises | fixed in 2.0.0 (C1) |
| Position | `size` | lots, float | > 0 while open | cleared to 0 when residual <= 1e-9 |
| Position | `tp_hit_mask` | int bitmask | bits 0..2 | slot identity used by partial exits; a zero leg sets its bit |
| Position | `tp{n}_price` | price, float or None | side-consistent after `reorder_remaining_targets` | None after a slot is consumed |
| Account | `balance`, `equity`, `open_pnl`, `daily_loss`, `max_drawdown` | USD, float64 | equity = balance + open_pnl after every valuation (one known exception, C4) | `daily_loss` and `max_drawdown` >= 0 |
| Account | `session_start_equity`, `session_start_balance` | USD | anchors set by `reset_daily` | |
| Guard | `daily_loss_limit_pct`, `max_loss_limit_initial_pct` | fraction in [0, 1] | | limits anchored to initial balance |
| Guard | `breach_reason` | enum | {`trailing_dd`, `max_drawdown`, `daily_loss`, None} | priority in this order |
| Guard | `guardrail_scope` | enum | {`rollout`, None} | any hard loss breach is `rollout` |
| Latch | `year_failed`, `breached_sessions`, `breach_log` | bool, set, list | rollout breach sets `year_failed` | non-episodic only |
| Pending order | `order_type`, `fill_quote`, `session_id`, `expiry_time` | enum, quote, int, timestamp | limit orders only | cancel reason `session_changed_before_limit_fill` (also `session_end_before_limit_fill`, `session_blocked_before_limit_fill` in source) |
| Sizing | `lots` | lots, float | [min_lot 0.01, max_lot 100] or 0 | grid is `lot_step`, floored |
| Sizing | `lot_step` | lots | > 0 | integer count of steps is the exact comparison |
| Targets | `tp_lot_fractions`, `ema_runner_fraction` | fraction | sums and runner in [0, 1] | |
| Candidates | `candidate_mask` | bool array | slot 0 (no-trade) always True; other slots True only when geometry is enabled and eligible | |
| Timing | bar timestamp | tz-aware datetime, canonical UTC | naive timestamps are rejected by `ftmo_trading_day` | |
| Session | mask | bool per bar | clock-time window, endpoints inclusive | mask only; rows are never removed |
| Reward | R reward | dimensionless | `pnl / fixed_risk_usd` | breach replaces the term with -10 |
| Reward | log growth reward | dimensionless | `scale * ln(E_after / E_before)` | `E_after <= 0` gives breach penalty |
| RNG | event stream | float64 bits | `SHA-256(seed:event_key)` seeds PCG64 | keyed per logical event |
| Event trace | ordering key | `(bar_index, phase_rank, seq)` | strictly increasing, unique | fixture convention for account traces |

Phase ranks used by account traces: 0 entry or open at the fill quote, 1 protective level (stop or target), 2 mark-to-market or valuation, 3 session boundary.

## 3. Timing and event order (source-verified)

- Decision at bar `t` fills at the open of bar `t + 1` (`episode_runtime.step`, `market_fill_idx = min(step_idx + 1, n - 1)`).
- Step `j` is valued at the bar index `env.step_idx` after the step. First valuation bar 61 on the synthetic tape, consecutive thereafter.
- Output `j` depends only on bars with index <= its valuation bar. Verified by perturbation at cuts 61, 64, 70 and by `test_output_depends_only_on_bars_up_to_its_valuation_index`.
- Per step, in order: market progression and mark-to-market at the current bar close, step constraints with stop and target checks on the current bar (`_check_sl_tp`), action execution at the fill quote, accounting, observation.
- A bar-close entry is effective at the bar's end. Its own high and low cannot trigger its stop (`position_has_completed_bar`).
- Stop fills: at the level, or at the bar's opening quote if the bar opens through the stop (worse fill). Long: `trigger = min(stop, open)`. Short: `trigger = max(stop, open_ask)`. Adverse slippage is then applied (`trading/execution/quotes.py`).
- Ambiguous bars: when both stop and target sit inside one bar with no tick book, the **stop wins** (sl is checked before tp in `_check_sl_tp`). Verified at env level by G3 scenarios.
- Limit orders: with `block_overnight`, a pending limit order is cancelled before any fill is considered when its session differs from the bar's session. Otherwise it fills at its quote's ask (long) when the quote time is inside the bar interval. A quote after the interval end leaves it pending.

## 4. Tolerance policy

The table lives in the fixture file (`tolerances`), so it is frozen with the expected values.

| Class | Rule | Applies to |
|---|---|---|
| `exact` | bit or string equality | integers, enums, reason codes, booleans, ISO timestamps, ordering keys, state counters, breach flags, RNG bit streams |
| `price_abs` | abs 1e-9 price units | quotes, fills, stop and target levels (float64 ulp at price 1e2..1e4 is about 1e-12) |
| `money_usd_abs` | abs 1e-6 USD | balances, equity, pnl, commission, margin, reserves, floors, capacities |
| `lots_abs` | abs 1e-9 lots | unquantized `compute_lots` output |
| `lot_step_exact` | integer step count exact; residual <= 1e-9 lots | any lot result on the broker grid |
| `ratio_abs` | abs 1e-12 | dimensionless account fractions |
| `log_reward_abs` | abs 1e-9 | log-growth reward |
| `reward_abs` | abs 1e-12 | R-multiple reward |

Risk decisions (breach or not, trade or no trade, margin accept or refuse, lot count, cancel or fill) are exact. Tolerances were fixed before the first replay of version 1.0.0 and were not changed to pass a case.

## 5. Disagreements and decisions

Classification uses the four plan categories: source defect, oracle defect, documented alternative semantics, backend defect.

| ID | Location | Observed in 1.0.0 | Decision and status in 2.0.0 |
|---|---|---|---|
| C1 | `trading/execution/costs.py` `CostModel.fill_price` | direction 0 returned bid | **Source defect, fixed in 2.0.0.** `fill_price` raises `ValueError` for any direction other than +1 or -1. QF-07 is an adverse positive. Every caller passes +1 or -1. |
| C2 | `CostModel.fill_price` vs `CostModel.total_cost` docstring | slippage 0.5 long returned ask 100.5; the `total_cost` docstring said slippage was modeled in `fill_price` | **Documented semantics, resolved in 2.1.0 (owner decision).** `fill_price` selects the quote side and does not apply `slippage_points`. Slippage is applied to the quote on the tick and protective paths before `fill_price`. The `total_cost` docstring was corrected, with no behaviour change. QF-08 is pinned at 100.5 by `test_fill_price_does_not_apply_slippage_points_double_count_guard`. Applying slippage inside `fill_price` would double count configured slippage (`config/base/default.yaml` `costs.slippage_points: 5.0`) on market and protective fills, so it is not done. |
| C3 | `trading/positions/multi_tp.py` `target_close_size` | zero leg returned the whole position | **Source defect, fixed in 2.0.0.** The function returns 0.0 for a zero leg, a runner-clamped leg, or an inactive slot. Three callers consume the slot without a broker close: `protective_level_runtime.py` (OHLC path and tick path) and `simulation/backtest/protective_management.py`. TG-05 is an adverse positive. Env regression: `test_zero_target_leg_consumes_slot_and_keeps_position`. The backtest caller is not runtime-tested here (O4). |
| C4 | `Broker.open_position` | equity not refreshed after open (balance 9998, equity 10000) | **Known broker-boundary limit, pinned (not a defect in the env path).** The env calls `mark_to_market` right after every open (`entry_execution_runtime.py`), which restores `equity = balance + open_pnl`. Pinned by `test_known_broker_boundary_limit_open_position_equity_is_refreshed_by_mark` (AC-A2). |
| SZ-14 | `compute_lots_with_execution_reserve` | budget 2.9, stop 10 returns 0.28 (hand 0.29) | **Documented rule, pinned, not changed.** Lots are `floor(affordable / lot_step) * lot_step` in float64, with no epsilon added. The sizer's comment explains why (a budget of 0.8999999999 must not round up). At exact lot multiples the float quotient can fall just below an integer (`0.29 / 0.01 = 28.999999999999996`), so the result is one step smaller. This is conservative and never breaches the risk budget. |
| TG-06, TG-07 | `target_close_size` rounding | leg 0.135 gave 0.14; 0.125 gives 0.12 | **Documented rule, pinned, not changed.** Target legs are `round(fraction * init_size, 2)`, Python round-half-even on the float64 value. Exact midpoints go to the even neighbour (0.125 to 0.12). Values stored just above a midpoint round up (0.135 to 0.14). The sizer floors and the leg rounds, so the two lot paths follow different rules. Unifying them is a behavior change for the owner. |
| SZ-08 | `compute_lots` zero risk | risk fraction 0 returns min_lot 0.01 | **Documented alternative semantics** (docstring: clipped to [min_lot, max_lot]). Risk concern for owner review. The execution-reserve sizer returns 0 for the same budget. Characterized, not changed. |
| QF-04 | `spread_points` | price units despite the name | **Documented alternative semantics** (units naming). Characterized. |
| RN-04 | event-keyed RNG | bit stream | **Characterization only** (SHA-256 is not hand-calculable). Golden for 2.0.0. |
| SS-01 | `ny_session_mask` | inclusive endpoints | **Characterization.** Owner to confirm the window convention. |
| E1 | `TradingEnv` at data end | observation differs from the in-episode observation at the same valuation index | **Documented alternative semantics, open.** A learner must not treat a truncated transition as a normal next state. Owner decision for LEARNER-CONTRACT truncation masking. |
| O5 | truncation observation (E1) | declared semantics, pinned by `test_declared_semantics_data_end_observation_is_not_the_in_episode_observation` | Closed for SEMANTIC-ORACLE. Decision on bootstrapping truncated transitions is handed to **LEARNER-CONTRACT**. |
| O6 | rounding, two declared rules | (a) lot sizer: `floor(affordable / lot_step) * lot_step` in float64, pinned by SZ-14 (0.28 at budget 2.9, hand 0.29). (b) target legs: `round(fraction * init_size, 2)` (Python round-half-even on float64), pinned by TG-06 (0.135 to 0.14) and TG-07 (0.125 to 0.12). | Closed for SEMANTIC-ORACLE: both rules documented as separate declared rules and pinned. No change. |

No oracle defect was found. Every expectation that disagreed with the source was re-checked by hand. Each kept expectation is the hand value, and each pinned rule is stated as a rule.

### Mutation evidence

The version 1.0.0 mutation run is recorded in `parity_report.md` section 4. Seven of eight mutants were killed. M8 survived on the invalid-direction branch of `fill_price`, which is now fixed (C1), so M8 is no longer an equivalent mutant there. The 2.0.0 mutation re-run is recorded in `parity_report.md` section 4.

## 6. Coverage matrix (version 2.0.0)

| Domain (plan list) | Positive | Adverse or boundary | Where | Status |
|---|---|---|---|---|
| timing (UTC, Prague day, DST) | TM-01..04 | TM-05 naive; zone-invariance property | fixture + properties | covered |
| bid/ask | QF-01, QF-02, QF-05, QF-06 | QF-03 zero spread; quote invariants | fixture + properties | covered |
| spread | QF-01, QF-04 | QF-03, QF-27 | fixture | covered (units caveat) |
| fees | QF-09 | QF-10, QF-11; commission partition AC-C, AC-C2 | fixture + scenario | covered |
| slippage | QF-12, QF-13, QF-18..22, QF-24, QF-08 (documented: fill_price ignores slippage) | QF-23 negative slippage | fixture + properties | covered; fill_price slippage pinned as documented semantics (C2) |
| lot and tick rounding | SZ-02, SZ-03, SZ-09, SZ-10, TG-01 | SZ-11, SZ-12, SZ-13, SZ-14 pinned, TG-03 | fixture + properties | covered; rules documented |
| partial fill | TG-01, TG-02, TG-04, AC-B | TG-03, TG-05 (C3 fixed); env zero-leg test | fixture + properties + env | covered |
| pending, cancel, replace | G1-cancel-session-change, G1-fill-within-interval | G1-session-change-beats-available-fill, G1-no-fill-after-interval | env scenarios | **cancel, fill and pending covered; replace is not_applicable** (no replace operation in source; grep evidence in fixture) |
| no-trade | env test `test_no_trade_action_keeps_flat_account_and_zero_reward` | | env | covered at env level |
| equity and margin | AC-A, AC-D, AC-D2 | AC-D refusal; C4 known limit | fixture | covered |
| daily reset | AC-A reset, AC-E | AC-F boundary; daily-floor property | fixture + properties | covered |
| breach latch | AC-E stateless guard, AC-F priorities; G4-control-opens | G4-breach-latch-blocks-entries (within session) | fixture + env | **partial: within-session covered; cross-session open (O3)** |
| gap bars | QF-14, QF-16 | QF-15, QF-17 (gap through stop) | fixture | covered (pure function) |
| ambiguous bars (both levels) | G3-both-levels-stop-wins, G3-tp-only | G3-sl-only-gap-free, G3-no-touch | env scenarios | covered |
| session mask | SS-01, SS-02 | window wrap and date-shift property | fixture + properties | covered |
| candidate mask and geometry | G2-disabled-candidate-mask | G2-disabled-ignores-setup-ids | env scenarios (SimpleNamespace) | **partial: disabled mask only; enabled-geometry mask open (O2)** |
| next observation | valuation-index test, prefix invariance | unused-field and future-append tests; E1 characterization | env tests | covered |
| reward components | RW-01, RW-02, RW-05 | RW-03, RW-04, RW-06, RW-07; telescoping property | fixture + properties | covered |
| terminal and truncation | data-end truncation, not terminated | E1 | env tests | partial: episode breach termination not covered at env level |
| RNG | RN-01..03 | RN-02, RN-03 distinct streams; order-independence property | fixture + properties | covered |

## 7. Open items and non-claims

Closed in 2.2.0 (positive and adverse cases pass, see parity report):

- **O2 enabled candidate-geometry mask:** the real `TradingEnv` with `trade_setup_actions`, `candidate_geometry_actions` and `agent_entry_execution` builds on a synthetic tape. The zone, age and distance seams are supplied per case. Positive: signal and valid zone make the market slot of candidate 19 eligible. Adverse: signal off gives only the no-trade slot, and a missing zone gives only the no-trade slot. The zone, age and distance inputs are seams (`mock.patch`), so the full causal feature path is not exercised here.
- **O3 cross-session latch:** `session_start="16:30"`, `session_end="23:00"`, `session_timezone="Etc/GMT-3"` make the 1500-bar two-day tape reach the second NY window (bars 1440 onward). Positive: control submits 58 entries in the second session. Adverse: a rollout breach in session 1 leaves zero submissions and zero opens in both sessions.
- **O4 backtest zero-leg caller:** `simulation/backtest/protective_management.py` `_record_target_slot` is driven directly. Positive: a 0.5-lot leg reaches `_record_close` with size 0.5. Adverse: a zero leg, and a runner-clamped zero leg, consume the slot with no close.

Declared for SEMANTIC-ORACLE, decision handed on:

- **O5 truncation observation:** the observation returned at data end is not the in-episode observation for the same valuation index. Pinned as current behaviour. **Decision for LEARNER-CONTRACT:** whether truncated transitions are bootstrapped, and how.
- **O6 rounding:** two separate declared rules (lot sizer floor; target-leg round-half-even), each pinned. **No change.** Unifying them would be an owner decision with a new evidence identity.

Run in this round (evidence in parity_report.md):

- **Native backend parity: run.** `qrl_native` is built from the worktree (release, worktree-local target) on a spool allocation without gcc, by linking through `rust-lld`. Parity tests in `native/python/tests/test_semantic_oracle_parity.py` replay the fixture expectations in cents: daily loss, floor, remaining capacity at and around the strict-below boundary, session-start capacity, and an integer-lot round trip (gross 4000 cents, fees 200 cents). The native API has integer lots only, so fractional-lot fixtures (AC-B) and the sizer, target-leg and quote families are Python-side by design and are not native.
- **Rust proptest: run.** `native/domain/tests/semantic_oracle_invariants.rs` uses a fixed seed (`semantic-oracle-domain-seed-0001`, 512 cases per property). Expected values are computed in i128. Covered: loss, floor, remaining capacity, the strict floor boundary, and the price and lot positivity rules.
- **Full env trace freeze: done.** `planning/native_modernization/semantic_oracle/fixtures/env_trace.v1.json` is a characterization frozen from the implementation (not hand-calculated), covering 60 steps and 76 trades on one fixed episode. Each record carries an ordering key: `[valuation_bar, action_ordinal, trade_seq]`. The replay test compares keys and types exactly, and reward and equity with the oracle tolerances.

Still not claimed:

- The 2.2.0 mutation re-run was not performed. It is not an acceptance item of this package.
- Feature causality (`CAUSAL-FEATURE-GRAPH`) is out of scope. Env tests hold features fixed.
- No claim about profitability, performance or research evidence.

## 8. Evidence identity changed by 2.0.0

- Source: `trading/execution/costs.py` (C1), `trading/positions/multi_tp.py` (C3), `simulation/environment/protective_level_runtime.py` (C3, two sites), `simulation/backtest/protective_management.py` (C3).
- Docstring only (C2): `CostModel.total_cost` docstring corrected. No behaviour change.
- Behavior change: a run that hits a zero-size target leg now keeps the position and consumes the slot, instead of exiting the whole position. A call to `fill_price` with an invalid side now raises. Existing evaluation evidence that depends on either path is **not** comparable with 2.0.0 and needs a new evidence identity.
- Fixtures: `semantic_oracle_fixtures.v2.json` and `MANIFEST.json` (2.0.0 and 2.1.0 superseded, digests recorded; 1.0.0 superseded earlier). 2.2.0 changes no expected value; it adds scenarios and the O4 test module.
- Config: `config/studies/profiles/{market_data,trading,simulation}.yaml` (registrations only).

## 9. Golden update policy

- Fixture values are never edited in place. A change bumps `fixture_version`, regenerates `MANIFEST.json` in the same change, records the decision in `changes_from_1_0_0`, and records the evidence it changes.
- Strict xfail cases become failures when a source fix makes them pass. That is the signal to move the case to positive and bump the version.
- Characterization and documented-rule values (RN-04, SS-01, TG-06, TG-07, SZ-14, SZ-08, QF-04) are labelled. They are not hand calculations of a correct behavior.
