# Reward and attribution contract

**Status:** draft
**Source of truth:** `simulation/environment/rewards.py`; `simulation/environment/accounting/step.py`; `simulation/environment/episode/info.py` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Step ledger inputs

| Field | Unit | Meaning |
|---|---|---|
| `equity_curve[-2:]` | Account currency | Previous and current marked equity |
| `_payout_withdrawn_this_step` | Account currency | Added back to step PnL to separate withdrawal from trading loss |
| `realized_close_pnl` | Account currency | PnL from closed quantity, if present |
| `realized_r` | R multiples | Closed outcome divided by initial risk, if present |
| `breach` | Boolean | Hard account breach overrides supported reward modes |
| `reward_parts` | Named floats | Components reported alongside the returned step reward |

## Mode and component contracts

- `equity_delta_r` requires fixed risk and positive `fixed_risk_usd`; it scores `step_pnl / fixed_risk_usd` (`simulation/environment/rewards.py`, `reward_initialization.py`).
- `survival` scores -1 hard breach, +1 completed breach-free split, otherwise zero (`simulation/environment/rewards.py`).
- `pnl` uses realized close PnL divided by initial balance and soft-band terms (`simulation/environment/rewards.py`).
- `rr` uses finite realized R on closing steps and soft-band terms (`simulation/environment/rewards.py`).
- `fit_reward_parts` reconciles named buckets to the clipped scalar (`simulation/environment/rewards.py`).
- The component names are `pnl`, `dsr`, `soft_daily`, `soft_year`, `soft_trailing`, `strategy`, `breach`, `sweep`, `peak_dd`, `peak_eod_dd`, `equity_growth`, and `survival` (`simulation/environment/rewards.py`).

See the [subject guide](../../subjects/C_trading_risk_execution/reward-and-attribution.md) and [reward reference](../rewards.md). Empirical objective quality is **not measured**.
