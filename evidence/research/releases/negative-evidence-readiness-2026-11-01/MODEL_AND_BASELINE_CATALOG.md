# Model and baseline catalog

## Policy semantics

The current setup catalog contains 6 idea families × 9 timeframes × 2
directions (108 setup categories), plus `NO_TRADE` (109 categorical choices).
These are masked alternatives. They are not 108 independent return
regressions. The hybrid actor selects a setup using a shared market
representation; in conditioned mode its selected setup embedding also
conditions execution actions. Multi-timeframe temporal encoders represent
historical observations, but that alone does not prove price-level-specific
expected returns, fill probabilities, or candidate lifetime modeling.

## Implemented baselines and evidence coverage

| Baseline tier | Current implementation | What is verified here | Missing for a scientific comparison |
|---|---|---|---|
| Always-flat / no-entry | `always_flat` is now a selectable, default reference in `scripts/research/analysis/evaluation/run_baseline_eval.py`, implemented as a zero-size step-indexed strategy and routed through the same `TradingEnv` report path. | Synthetic smoke test passed: zero positions and zero PnL; the 2026 default split is labeled `exposed_report_only`. | No current-source market evaluation is promoted. The shared continuous baseline evaluator is not yet a matched registry for every RL action schema. |
| Random eligible action | No random-eligible strategy found in `trading/baselines/`. | No empirical evidence. | Implement eligibility-aware seeded sampling under the same action and risk contracts; record seeds and action denominators. |
| Simple rules | `BuyAndHoldStrategy`, `EMAMACDRSIStrategy`, `MultiLevelBreakoutStrategy`, and `SessionMomentumStrategy` in `trading/baselines/classical.py`; `run_baseline_eval.py` routes these through `TradingEnv`. Separate signal helpers are in `rule_based.py`. | Synthetic unit tests cover strategy signals; a smoke integration test covers report creation. The evaluator defaults to buy/hold, EMA/MACD/RSI, and breakout; session momentum requires explicit selection. | No current-source matched real-data evaluation is promoted. Freeze one rule, period, costs, risk settings, and action semantics before comparing. |
| Supervised candidate model | `LSTMSweepClassifier`/`LSTMStrategy` in `trading/baselines/lstm_classifier.py`; training entry point is `training/runner/lstm_baseline.py`. | Code and isolated implementation tests exist. | No audited label horizon/purge, calibrated eligible-candidate comparison, or matched full-path risk result is established. |
| Cash / buy-and-hold reference | `cash_hold.py` has a separate train-sized US100 long-hold calculation; classical module also includes simple buy-and-hold signals. | Unit tests exercise the analytical sizing and accounting helper. | The cash-hold calculation is not an identical candidate-policy evaluation; its hard-coded contract/swap inputs need source verification and a common evaluation wrapper. |
| Theoretical comparator | None in the evaluated baseline registry. | No empirical evidence. | Define a non-deployable, explicitly non-comparable upper bound only if its information set and hindsight use can be bounded and labeled. |
| RL controls | Hybrid/setup-conditioned PPO screens and the selected P6 matched pair. | One-seed 100k negative screens; selected seed-50 P6 pair failed both training risk gates. | Independent seeds, full matched baseline set, cost stress, and untouched confirmation are absent. |

Source review: [baseline evaluator](../../../../scripts/research/analysis/evaluation/run_baseline_eval.py), [classical strategies](../../../../trading/baselines/classical.py), [supervised baseline](../../../../trading/baselines/lstm_classifier.py), [test coverage index](FUNCTION_TEST_EVIDENCE_INDEX.csv). No baseline performance ranking is inferred from code presence or synthetic tests.

## Evidence-backed RL models

| Model/evidence | Status | Claim boundary |
|---|---|---|
| Hybrid PPO, 100k | Negative screen | One seed; full 2025 replay breached maximum loss. |
| Setup-conditioned PPO, 100k | Negative screen | One seed; full 2025 replay breached maximum loss. |
| Selected matched P6 A4A/A4B, 2M | Failed the historical strict zero-breach gate under legacy risk semantics | One seed; both negative and both full data splits completed. The March `daily_loss` events use a gross-negative-close counter that ignores positive closes; they are not net daily-equity breaches. A4B also had a later maximum-drawdown event. A4A's aggregate ledger endpoint was above the floor. See the [risk-gate trace](P6_RISK_GATE_SEMANTICS_AND_BREACH_TRACE.md). |
| MTF encoder throughput comparison | Engineering measurement | Runtime comparison only; no trading viability claim. |
| Candidate geometry/history model | Proposed, untested | No new model implementation or training is justified until source/label integrity and a registered question pass earlier gates. |

## Comparative conclusion

Implementations exist for several baseline types, but a complete matched
registry of always-flat, randomized, deterministic rules, supervised scorers,
RL controls, and theoretical upper bounds under identical executable prices,
costs, risk rules, sample periods, and uncertainty methods does not. Do not
claim comparative superiority or select a deployable model. The supported
decision is **no model has demonstrated an economic edge**.

## Recommended next scientific comparison

Only after current-source data, event labels, and execution chronology pass
their gates, preregister a single-factor matched comparison. Keep the
existing setup-conditioned policy as a control. A price-aware candidate scorer
is a hypothesis, not a guaranteed improvement. Specify candidate entry/stop/
target geometry, order expiration, fill censoring, training-only calibration,
costs, risk gate, seeds, and a non-exposed validation design before fitting.
