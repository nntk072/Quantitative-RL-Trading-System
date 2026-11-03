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
balance from its first-session realized closes. The cross-engine lifecycle
does not match in bar-only fallback mode: `TradingEnv` uses the next bar's open
quote/time, while `run_backtest` uses the next bar's close quote/time. The
selected research run requires TickBook execution and fails closed when tick
input is unavailable; the separate 23-pair packet covers that configured tick
path. This trace is an alternate-mode limitation, not a learned-policy result
or strategy comparison.

The packet also contains a separate two-session trace through the selected
TickBook path with required execution and 30 ms latency. Environment and
backtest fills, closes, session resets, and final account state match for the
controlled actions. A companion $1 daily-loss scenario confirms that both
engines record a daily breach, block an attempted same-session re-entry, reset
on the next local session ID, and allow a next-session entry. Independent
verification reports recompute event/account arithmetic and input/source
hashes. A third controlled case verifies the episodic max-loss close: both
engines use the same selected TickBook quote and match close PnL and breach-time
equity/daily loss; final daily-loss counters are not compared across different
terminal horizons. These are bounded simulator traces, not policy replays.
They do not close the broader lifecycle matrix, feed-wide tie/missing-quote
chronology, or live-account parity. See
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
