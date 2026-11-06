# Early reset abort semantics

## Contract

Calling `TradingEnv.reset()` before a terminal transition aborts the current
episode. Reset clears the open position, pending entry, account state, payout
and breach counters, and episode-local trade/equity ledger. It does not close
the position, realize its open PnL, or emit a payout or breach event. This
behavior is suitable for restarting a simulation episode; it must not be
counted as a completed trading result.

Configured data-end and `max_episode_steps` transitions are different: the
accounting step liquidates an open position before returning the terminal or
truncated transition. Evaluation that needs realized outcomes must use those
configured boundaries rather than manually resetting an active environment.

## Verification

The current-source regression opens a position, resets the active environment
with the same seed, and checks that account/position/ledger/payout state is
cleared and that the new observation matches a fresh environment. The focused
test passes 1/1. The source and test snapshots are hashed in
`SOURCE_SHA256SUMS`; the run command and result are in `run_metadata.json` and
`focused_tests.log`.

This verifies reset semantics only. It does not provide environment/backtest
cashflow parity for an external abort, full-ledger daily-risk reconciliation,
or checkpoint-backed policy replay determinism.
