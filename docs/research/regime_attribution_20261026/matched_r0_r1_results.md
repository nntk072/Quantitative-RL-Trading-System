# Matched R0/R1 D1 normalization screen

This is a one-seed development comparison. The 2026 split is report-only and had been inspected before this experiment; it is not confirmatory evidence.

## Campaign identity

| Arm | Campaign | Git revision | Fingerprint | Summary SHA-256 |
|---|---|---|---|---|
| R0 control | `sustainable_growth_seed50_train2025_20261025_2m_normal_v1` | `002f6b0fc09346560e19c800961fc458fbc3f5f2` | `50bb89f7e463acefaab800f287e6bf988b13dde724c6a52930e092a3bde1ea37` | `283c2d3a551531bf62082566f7ddfb67e7e6cc2f9c5c6df924f7c54513c6edc2` |
| R1 treatment | `regime_d1_norm_r1_seed50_train2025_20261026_2m_normal_retry1_v1` | `6bc0697f7072b592dd2b2593911d688d2e1d946c` | `b19f0f7e941d416d42aa6329559e843710ed5ffd9c0cf1cddaafc664a70979b9` | `cc74c93325f916f2bb4d5c374680cce1ea6cc6f155b6dcf237c1dff18cfe1f09` |

Matched settings: 2,000,000 steps per variant, seed 50, 8 environments, data source `bundle`, stochastic evaluation (`deterministic=false`).

The only intended intervention is recorded in `matched_pair.json`: source-index normalization of selected D1 technical features before causal alignment. PPO, TCN, action schema, risk policy, dataset, split, seed, and training budget are otherwise matched.

## Metrics

Each delta is R1 minus R0. Training metrics are in-sample. Testing metrics come from the previously exposed report-only split.

| Split | Metric | R0 | R1 | Delta |
|---|---|---:|---:|---:|
| Train | Net return | -10.15% | -9.98% | 0.175 pp |
| Train | Net PnL | -$10,152.53 | -$9,977.86 | $174.66 |
| Train | Maximum drawdown | 36.69% | 31.13% | -5.554 pp |
| Train | Sharpe | -0.371 | -0.465 | -0.093 |
| Train | Profit factor | 0.965 | 0.949 | -0.016 |
| Train | Win rate | 42.79% | 41.64% | -1.155 pp |
| Train | Expectancy per trade | -$9.15 | -$11.35 | -$2.20 |
| Train | Trades | 1,110 | 879 | -231 |
| Train | Days traded / available | 209/259 | 177/259 | — |
| Train | Full-period survival | No | No | — |
| Train | Risk gate | max_loss_stopped_trading | max_loss_stopped_trading | — |
| Test | Net return | -10.07% | -10.07% | -0.005 pp |
| Test | Net PnL | -$10,066.31 | -$10,070.91 | -$4.60 |
| Test | Maximum drawdown | 29.04% | 21.59% | -7.454 pp |
| Test | Sharpe | -0.495 | -0.576 | -0.081 |
| Test | Profit factor | 0.947 | 0.929 | -0.018 |
| Test | Win rate | 41.87% | 38.59% | -3.281 pp |
| Test | Expectancy per trade | -$14.74 | -$17.27 | -$2.54 |
| Test | Trades | 683 | 583 | -100 |
| Test | Days traded / available | 127/205 | 115/205 | — |
| Test | Full-period survival | No | No | — |

## Coverage and interpretation limits

| Measure | R0 | R1 |
|---|---:|---:|
| Full training-split episodes | 16 | 16 |
| Environments with a full-split episode | 8 | 8 |

This single-seed screen can show whether restoring D1 feature availability changed this run. It cannot establish statistical superiority or prove that feature availability caused any metric difference. See the full generated R1 report and the R1 causal regime attribution for trade-level evidence.
