# Daily regime feature normalization: comparison result

## Research question

Does normalizing selected daily-market features on their own daily timeline,
before aligning them to minute decisions, improve an otherwise matched PPO
policy?

## Comparison

The control normalized the assembled feature stream after higher-timeframe
values had been repeated across minute rows. The treatment normalized selected
daily features on the daily source timeline before causal alignment. Both
policies used the same PPO setup, market data, account rules, trading actions,
execution assumptions, seed, and training budget.

## Observed outcomes

| Period and measure | Control | Source-timeframe normalization | Change |
|---|---:|---:|---:|
| Training net return | −10.15% | −9.98% | +0.18 percentage points |
| Training maximum drawdown | 36.69% | 31.13% | −5.55 percentage points |
| Training Sharpe | −0.371 | −0.465 | Lower |
| Training profit factor | 0.965 | 0.949 | Lower |
| Training win rate | 42.79% | 41.64% | Lower |
| Training expectancy per trade | −$9.15 | −$11.35 | Lower |
| Training trades | 1,110 | 879 | 231 fewer |
| Training survival | Failed | Failed | No change |
| Report-only net return | −10.07% | −10.07% | Essentially unchanged |
| Report-only maximum drawdown | 29.04% | 21.59% | −7.45 percentage points |
| Report-only Sharpe | −0.495 | −0.576 | Lower |
| Report-only profit factor | 0.947 | 0.929 | Lower |
| Report-only win rate | 41.87% | 38.59% | Lower |
| Report-only expectancy per trade | −$14.74 | −$17.27 | Lower |
| Report-only trades | 683 | 583 | 100 fewer |

## Interpretation

The treatment modestly reduced the training loss and drawdown, but worsened
several trade-quality measures and did not survive the account loss limit. On
the previously inspected report-only interval, net return was effectively
unchanged while Sharpe, profit factor, win rate, and expectancy were worse.
The result does not support promoting this normalization change as a trading
improvement.

## Limits

This is a one-seed comparison. The report-only interval had already been
inspected and is not confirmatory evidence. The comparison tests one feature
normalization change; it does not show that daily regime context is generally
useful or harmful. Detailed position-level regime tables are retained in the
external research archive.
