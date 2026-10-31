# Evaluation metrics

The core performance metric record is computed from a chronological equity
curve and, where available, completed-position trade outcomes.

| Metric | Meaning |
|---|---|
| Sharpe | Annualized mean simple bar return divided by its dispersion under the selected period scale. |
| Sortino | Annualized return relative to downside deviation. |
| Calmar | Annualized return divided by maximum drawdown. |
| Maximum drawdown | Largest peak-to-trough equity decline as a positive fraction. |
| Total return / PnL | End-to-start account return and absolute equity change. |
| Profit factor | Gross positive trade PnL divided by absolute gross negative trade PnL. |
| Win rate | Fraction of completed trades with positive net PnL. |
| Expectancy | Mean net PnL per completed trade. |
| Breach count / rate | Caller-recorded breach events and the fraction of sessions with a breach. |
| Turnover | Trade count relative to evaluated bars. |
| Maximum consecutive loss | Longest consecutive losing-trade sequence. |

Position-aware records aggregate partial fills into one completed position for
trade statistics; fill count and incomplete-position count are separate.
Metric units, annualization frequency, costs, and sample size must accompany a
reported value. A ratio is not reliable evidence when the return or trade
sample is too small.

This reference describes the core metric record. Specialized analysis such
as action diversity, setup selection, exit reasons, and cost attribution is
reported separately. See the [evaluation guide](../modules/evaluation.md).
