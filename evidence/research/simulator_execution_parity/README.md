# Simulator execution parity

## Local TickBook action trace

`local_tick_action_trace.json` records a controlled entry/exit replay through
both `TradingEnv` and `run_backtest`. The replay uses the current training
US100 M1 bars and tick CSV, the production `build_tick_book` parser, the
configured 0.25 price grid, and the `Etc/GMT-3` timestamp label. It selects two
historical quote groups from the existing fill-to-tick alignment report only
when each group has one raw row, both quote sides are present on that row, and
the current TickBook selects the same timestamp and prices at the M1 order
time.

The selected groups are 2024-12-30 13:50:00.071 UTC for the long entry and
2024-12-30 14:42:00.078 UTC for the exit quote, 52 minutes later. The action
sequence is controlled; it does not reproduce either historical campaign
policy. The report compares the source decision bar, order submission, fill
timestamp and price, close PnL, and ending account balance. The current replay
passes with equal fills and account totals in both engines.

This validates one bounded local-data path through the current parser and
simulators. It does not establish provider-clock or calendar authority,
within-timestamp chronology for other rows, a strategy result, or broker
execution behavior. The overall feed still contains timestamp ties and
missing-side rows, so this trace does not close all feed or lifecycle gates.

## Monthly and direction coverage

`local_tick_action_trace_set.json` extends the single trace to 23 controlled
entry/exit pairs selected from source quote groups that are unique, complete,
and resolved to the same timestamp and prices by the current `TickBook`. It
covers January–December 2025 and both long and short actions; May has one
eligible short pair. Selection uses source quality and chronological
month/direction strata, not reported PnL. Each pair independently reconciles
environment/backtest entry and exit source, timestamps, prices, close PnL, and
ending balance.

This is broader local-feed execution coverage, not a historical policy replay
or a campaign result. The 23 pairs are the eligible sample under the declared
quote-group and same-date/60-minute rules; they do not represent every fill or
all feed rows. They do not resolve tied-timestamp chronology, session-clock
authority, provider semantics, market impact, or broker behavior. The earlier
52-minute trace remains preserved as a separate two-fill fixture.

`local_tick_action_trace_set_stratified.json` adds a larger, deterministic
2025-only sample using the same quote-quality and TickBook-resolution gates.
It selected 58 controlled pairs across 23 of the 24 month/direction strata,
with up to three pairs per stratum and no source event reused. Every pair
passed environment/backtest checks for tick source, fill time and price,
source decision bar, close PnL, and ending balance. The missing stratum is
May-long; pair availability is determined by the source-quote criteria, not
by PnL. These are independent one-position trace fixtures, not statistically
independent observations, historical policy replays, portfolio lifecycle
coverage, or economic results. Existing tie, feed, account, and live-parity
limits still apply.

The independent check
`local_tick_action_trace_set_stratified_verification.json` rehashes the tick,
bar, alignment, and generator inputs; checks persisted source-ledger/event
identities for reuse; and recomputes reported fill, price, PnL, and balance
comparisons plus the single-trade `initial_balance + net_pnl = ending_balance`
bridge. It validates packet consistency and provenance, not either
simulator's implementation independently.

Reproduce the expanded sample inside a compatible existing allocation with:

```bash
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_tick_trace.py \
  --start-month 2025-01 --end-month 2025-12 \
  --max-trace-pairs 72 --max-pairs-per-stratum 3 \
  --out evidence/research/simulator_execution_parity/local_tick_action_trace_set_stratified.json
.venv/bin/python scripts/research/analysis/evaluation/verify_simulator_local_tick_trace_set.py \
  --report evidence/research/simulator_execution_parity/local_tick_action_trace_set_stratified.json
```

## Fail-closed quote-wait gap

`quote_wait_gap/` pairs the training environment and event-driven backtest on
the same synthetic entry case. The only quote arrives 2 ms after the scheduled
fill while both engines have a 1 ms maximum quote wait. Both raise
`TickExecutionUnavailable`; neither substitutes a candle quote. This verifies
the configured local fail-closed contract for one controlled gap. It does not
measure empirical staleness thresholds or establish feed-wide execution
availability. The focused test is
`tests/integration/backtest/test_account_transition_parity.py::test_environment_and_backtest_both_fail_closed_on_quote_wait_gap`.

`tied_protective_trigger_order/` verifies the current deterministic tie rule
when the first of two source-ordered quotes sharing a millisecond timestamp
crosses the stop and the second crosses the target. Both engines close at the
first quote and reconcile account balance. Source order is an implementation
tie-break only; it does not establish true sub-millisecond market chronology.

The focused [`controlled action and account parity suite`](controlled_action_account_parity/README.md)
passes 23/23 cases in the existing GH200 allocation. It covers several current
controlled cross-engine contracts, while the complete lifecycle acceptance
matrix remains open.

## Local session-account transition

`local_session_account_transition/session_account_transition.json` compares
the environment and event backtest on prescribed actions across two
date-derived training sessions. Each engine resets its own session-start
balance from its first-session realized closes. A previously observed
bar-fallback mismatch is fixed: `run_backtest` now uses the same next-bar-open
quote and timestamp as `TradingEnv`. The refreshed two-session trace and its
independent verifier pass. The selected research run still requires TickBook
execution and fails closed when tick input is unavailable; the separate
23-pair packet covers that configured tick path. This is controlled parity
evidence, not a learned-policy result or strategy comparison.

The packet also contains a separate two-session trace through the selected
TickBook path with required execution and 30 ms latency. Environment and
backtest fills, closes, session resets, and final account state match for the
controlled actions. A historical $1 daily-loss trace records the earlier
behavior: it blocks same-session re-entry, resets on the next local session
ID, and allows a next-session entry. That output is preserved and superseded by
[`daily_breach_full_evaluation_failure/`](daily_breach_full_evaluation_failure/README.md),
which independently verifies that both engines latch account failure and
block later-session entries after a daily breach. A third controlled case
verifies the episodic max-loss close: both engines use the same selected
TickBook quote and match close PnL and breach-time equity/daily loss; final
daily-loss counters are not compared across different terminal horizons.
These are bounded simulator traces, not policy replays. They do not close the
broader lifecycle matrix, feed-wide tie/missing-quote chronology, or
live-account parity. See
`local_session_account_transition/README.md`.

## Scheduled session close

`scheduled_session_close/` records and independently verifies a controlled
final-NY-bar TickBook close at zero and configured 30 ms randomized latency.
It documents the former submission-window mismatch and the corrected shared
deadline resolution. The fixture includes sub-minute quote rows and confirms
matching scheduled-close arrivals, fills, and account state in both engines.
Other execution events and the broader lifecycle gate remain open.

## Position stop lifecycle

`position_stop_lifecycle/` records 26 shared stop-helper unit cases and 16
paired synthetic lifecycle cases. Environment and backtest now use one shared
confirmed-swing stop calculation. The paired cases cover breakeven and
confirmed-swing trailing updates, next-bar effectivity, protective close
outcomes, account guardrails, and session close. Exact output and current source
hashes are recorded in the packet. This does not close financing,
checkpoint/replay, historical-policy, or complete account/cashflow parity.

Reproduce the sampled trace set with the same current inputs:

```bash
.venv-x86/bin/python -m scripts.research.analysis.evaluation.compare_simulator_local_tick_trace \
  --ticks-csv data/training/US100.cash_202412300105_202610162349.csv \
  --bars-csv data/training/US100.cash_M1_202412300105_202610162349.csv \
  --alignment-report evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json \
  --timezone Etc/GMT-3 \
  --max-hold-minutes 60 \
  --max-trace-pairs 26 \
  --out evidence/research/simulator_execution_parity/local_tick_action_trace_set.json
```

The generator streams the 2.5 GB local tick export; run it on an appropriate
compute node, not the login host.

## Reproduction

Run the generator from the repository root inside a suitable existing compute
allocation. On the current GH200 allocation, use the ARM64 `.venv/bin/python`
through the persistent allocation tmux shell. It streams the local tick input
using the production TickBook builder and does not create child Slurm steps.

```bash
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_tick_trace.py \
  --ticks-csv data/training/US100.cash_202412300105_202610162349.csv \
  --bars-csv data/training/US100.cash_M1_202412300105_202610162349.csv \
  --alignment-report evidence/research/fill_quote_source_alignment/selected_campaign_fill_quote_alignment.json \
  --timezone Etc/GMT-3 \
  --max-hold-minutes 60 \
  --out evidence/research/simulator_execution_parity/local_tick_action_trace.json
```

The JSON records source hashes, selected quote-group metadata, simulator
settings, and both event ledgers. Raw market data is not included.

## Verification

```bash
.venv-x86/bin/python -m pytest tests/integration/backtest/test_local_tick_action_trace.py -q
```

## Paired lifecycle characterization

`paired_lifecycle_characterization/` records a consolidated current-source run
of seven integration modules. It passed 69/69 tests in the existing GH200
allocation, spanning account transitions, protective exits, risk lifecycle,
repeated payouts, fill accounting, quote parity, and local TickBook traces.
Exact output and test/source hashes are included. This strengthens bounded
contract coverage; it does not close the broader lifecycle/accounting gate or
historical policy linkage.

## Selected-run maximum-loss events

`max_loss_event_reconciliation/` independently checks hard maximum-loss breach
rows against the four saved A4 equity series and the pinned initial-equity
allowance. Three recorded events match both the first sampled crossing below
$90,000 and an exact saved equity value; the A4A training partition has no
crossing or event. The configs do not record `max_drawdown_mode`, so the packet
verifies only the $90,000 initial-equity floor and does not infer EOD or
intraday ratchets. It does not replay the historical policies or close the
broader Stage E accounting gate.
