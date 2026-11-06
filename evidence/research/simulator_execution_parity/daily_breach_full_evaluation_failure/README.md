# Daily breach fails the full evaluation

This packet verifies the selected account rule: any daily-floor breach
permanently fails the full account/evaluation. The 5% daily allowance is still
measured from the supplied session-opening equity and includes open PnL. A
touch exactly at the floor is allowed; a breach means equity below the floor.
On a breach, both engines force-close the position, reject later entries in the same
session and later sessions, and record the account as failed. Non-episodic
rollouts may continue for training data collection, but those accounts do not
survive evaluation.

The controlled trace uses two local date-derived session IDs and a $1 daily
limit to make the breach observable. Environment and event-backtest fill,
breach, close, account, and entry-block events match. The independent verifier
recomputes lifecycle/account parity and checks the raw bar/tick and source-code
hashes. Result: trace matched; independent verification passed. This is a
synthetic contract trace, not a learned-policy replay, a market-performance
estimate, or evidence about unobserved campaign paths.

The historical `local_session_account_transition/session_tick_daily_loss_reset.json`
packet records the former next-session-recovery behavior. It remains
unchanged and is superseded for new evaluations by this packet.

## Reproduction

Run inside a compatible existing allocation; the generator reads the supplied
local training M1 bar and tick exports.

```bash
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py \
  --scenario daily_loss_full_evaluation_failure \
  --ticks-csv data/training/US100.cash_202412300105_202610162349.csv \
  --out "$PWD/evidence/research/simulator_execution_parity/daily_breach_full_evaluation_failure/daily_breach_full_evaluation_failure.json"
.venv/bin/python scripts/research/analysis/evaluation/verify_simulator_local_session_account_trace.py \
  evidence/research/simulator_execution_parity/daily_breach_full_evaluation_failure/daily_breach_full_evaluation_failure.json
```

`OUTPUT_SHA256SUMS` covers this report, its independent verification, and the
human interpretation. `SOURCE_SHA256SUMS` records the implementation and
focused regression inputs. The report itself records hashes for the exact
bar/tick inputs and code used to generate it.
