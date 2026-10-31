# Reward modes

The active reward is selected by the resolved environment configuration. The
mode name alone is insufficient to reconstruct a reward if additional
components or constraints are enabled.

| Mode | Primary signal | Key interpretation limit |
|---|---|---|
| `dsr` | Differential Sharpe update from the reward's running return moments. | A shaped stepwise objective, not terminal account return. |
| `pnl` | Realized PnL-oriented reward. | Open-position mark-to-market and composite terms depend on configuration. |
| `rr` | Realized trade R-multiple reward. | Requires meaningful initial risk and complete trade accounting. |
| `equity_delta_r` | Equity change normalized by configured fixed dollar risk. | Requires fixed risk configuration. |
| `equity_log_growth` | Logarithmic equity change. | Discounted PPO reward is not identical to undiscounted terminal log growth. |

Some strategy rewards can compose additional terms with supported base modes;
other modes reject incompatible sweep/structure terms. The environment records
reward parts for diagnosis. Do not double-charge spread or slippage that has
already been included in account equity.

Use the [reward concept](../concepts/rewards.md) for interpretation and inspect
the resolved configuration and run manifest for exact scales, constraints,
and component weights.
