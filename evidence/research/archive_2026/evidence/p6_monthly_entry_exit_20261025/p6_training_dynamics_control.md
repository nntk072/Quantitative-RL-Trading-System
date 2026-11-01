# P6 Training-Year Policy Dynamics and Non-PPO Control

This report describes the P6 training partition from 2024-12-30 through 2025-12-31. It does not use the 2026 report split. The non-PPO control is the repository’s causal `SessionMomentumStrategy`, run on the same A4B environment, training bars, features, bid/ask tickbook, risk configuration, and seeded execution latency. It is an in-sample rule reference, not a fresh holdout or matched-entry ablation.

The PPO ledger records only entry-intent decisions as `open` or `reject`; no-op actions and actions taken while a position is open are not written in the trade ledger. Therefore PPO action mix below means action mix on logged entry intents, not on every policy decision. Monthly decision denominators come from the saved policy equity curve rows. The rule control action mix counts every environment decision.

## Monthly PPO entry behavior

| Variant | Month | Steps | Intents | Trades opened | Rejects | Intents / 1k steps | Trades / 1k steps | Intent acceptance | Long / short / neutral intent share | Mean intensity | Mean risk action |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2024-12 | 782 | 334 | 12 | 322 | 427.11 | 15.35 | 3.6% | 61.7% / 38.3% / 0.0% | 0.450 | 0.026 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-01 | 8030 | 4039 | 81 | 3958 | 502.99 | 10.09 | 2.0% | 55.0% / 45.0% / 0.0% | 0.498 | 0.006 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-02 | 7639 | 3548 | 88 | 3460 | 464.46 | 11.52 | 2.5% | 56.0% / 44.0% / 0.0% | 0.504 | 0.019 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-03 | 8211 | 3711 | 100 | 3611 | 451.95 | 12.18 | 2.7% | 57.0% / 43.0% / 0.0% | 0.480 | 0.022 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-04 | 8211 | 3606 | 90 | 3516 | 439.17 | 10.96 | 2.5% | 55.6% / 44.4% / 0.0% | 0.497 | 0.017 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-05 | 8421 | 3952 | 73 | 3879 | 469.30 | 8.67 | 1.8% | 52.3% / 47.7% / 0.0% | 0.508 | 0.004 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-06 | 8030 | 4019 | 104 | 3915 | 500.50 | 12.95 | 2.6% | 52.6% / 47.4% / 0.0% | 0.500 | 0.016 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-07 | 8646 | 3692 | 45 | 3647 | 427.02 | 5.20 | 1.2% | 57.1% / 42.9% / 0.0% | 0.514 | 0.012 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-08 | 8211 | 4486 | 55 | 4431 | 546.34 | 6.70 | 1.2% | 55.9% / 44.1% / 0.0% | 0.499 | -0.000 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-09 | 8421 | 4038 | 62 | 3976 | 479.52 | 7.36 | 1.5% | 54.1% / 45.9% / 0.0% | 0.496 | 0.034 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-10 | 8993 | 4319 | 122 | 4197 | 480.26 | 13.57 | 2.8% | 51.1% / 48.9% / 0.0% | 0.499 | 0.005 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-11 | 7473 | 3542 | 80 | 3462 | 473.97 | 10.71 | 2.3% | 56.4% / 43.6% / 0.0% | 0.516 | 0.002 |
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 2025-12 | 8424 | 4420 | 75 | 4345 | 524.69 | 8.90 | 1.7% | 55.7% / 44.3% / 0.0% | 0.501 | 0.022 |
| `ladder_a4b_entry_fsm_qgrid025` | 2024-12 | 782 | 334 | 12 | 322 | 427.11 | 15.35 | 3.6% | 44.6% / 55.4% / 0.0% | 0.515 | -0.031 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-01 | 8030 | 3922 | 83 | 3839 | 488.42 | 10.34 | 2.1% | 37.1% / 62.9% / 0.0% | 0.561 | -0.048 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-02 | 7639 | 3047 | 83 | 2964 | 398.87 | 10.87 | 2.7% | 40.1% / 59.9% / 0.0% | 0.571 | -0.040 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-03 | 8211 | 3754 | 100 | 3654 | 457.19 | 12.18 | 2.7% | 42.1% / 57.9% / 0.0% | 0.552 | -0.032 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-04 | 8211 | 4099 | 104 | 3995 | 499.21 | 12.67 | 2.5% | 39.7% / 60.3% / 0.0% | 0.566 | -0.031 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-05 | 8421 | 3923 | 67 | 3856 | 465.86 | 7.96 | 1.7% | 36.9% / 63.1% / 0.0% | 0.575 | -0.048 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-06 | 8030 | 4069 | 102 | 3967 | 506.72 | 12.70 | 2.5% | 37.0% / 63.0% / 0.0% | 0.567 | -0.039 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-07 | 8646 | 3724 | 47 | 3677 | 430.72 | 5.44 | 1.3% | 39.7% / 60.3% / 0.0% | 0.579 | -0.044 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-08 | 8211 | 4436 | 52 | 4384 | 540.25 | 6.33 | 1.2% | 38.8% / 61.2% / 0.0% | 0.567 | -0.057 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-09 | 8421 | 4133 | 64 | 4069 | 490.80 | 7.60 | 1.5% | 37.5% / 62.5% / 0.0% | 0.560 | -0.025 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-10 | 8993 | 4776 | 111 | 4665 | 531.08 | 12.34 | 2.3% | 35.4% / 64.6% / 0.0% | 0.559 | -0.050 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-11 | 7473 | 5336 | 0 | 5336 | 714.04 | 0.00 | 0.0% | 38.1% / 61.9% / 0.0% | 0.572 | -0.051 |
| `ladder_a4b_entry_fsm_qgrid025` | 2025-12 | 8424 | 6729 | 0 | 6729 | 798.79 | 0.00 | 0.0% | 36.9% / 63.1% / 0.0% | 0.564 | -0.043 |

## Monthly non-PPO reference

| Month | Steps | Trades opened | Completed trades | Trades / 1k steps | Long / short / flat action share | Mean net R | Net P&L | Win rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 782 | 18 | 18 | 23.02 | 0.0% / 0.0% / 100.0% | -0.5683 | $-4191.04 | 27.8% |
| 2025-01 | 8030 | 98 | 98 | 12.20 | 9.7% / 14.6% / 75.7% | 0.0884 | $3460.94 | 46.9% |
| 2025-02 | 7639 | 99 | 99 | 12.96 | 10.2% / 15.4% / 74.4% | 0.2596 | $9905.67 | 52.5% |
| 2025-03 | 8211 | 121 | 121 | 14.74 | 14.3% / 12.1% / 73.6% | 0.3310 | $16981.67 | 43.8% |
| 2025-04 | 8211 | 119 | 119 | 14.49 | 19.0% / 9.5% / 71.4% | -0.1245 | $-7508.67 | 46.2% |
| 2025-05 | 8421 | 99 | 99 | 11.76 | 20.3% / 9.3% / 70.4% | -0.1717 | $-7530.47 | 42.4% |
| 2025-06 | 8030 | 108 | 108 | 13.45 | 25.1% / 2.9% / 72.0% | 0.0172 | $711.11 | 49.1% |
| 2025-07 | 8646 | 70 | 70 | 8.10 | 9.0% / 20.0% / 71.0% | -0.1648 | $-4630.14 | 42.9% |
| 2025-08 | 8211 | 78 | 78 | 9.50 | 14.3% / 14.3% / 71.4% | -0.0834 | $-2350.56 | 35.9% |
| 2025-09 | 8421 | 90 | 90 | 10.69 | 9.3% / 18.6% / 72.1% | -0.1546 | $-5492.35 | 36.7% |
| 2025-10 | 8993 | 136 | 136 | 15.12 | 25.9% / 4.3% / 69.7% | -0.1253 | $-7057.47 | 41.2% |
| 2025-11 | 7473 | 21 | 21 | 2.81 | 10.7% / 15.7% / 73.6% | -0.3020 | $-2321.41 | 33.3% |
| 2025-12 | 8424 | 0 | 0 | 0.00 | 13.9% / 13.9% / 72.2% | nan | $0.00 | nan% |

The per-trade rule ledger is tick sourced; monthly net R and P&L for completed positions are in `p6_session_momentum_monthly_control.csv`.

## P6 net expectancy as observed

| Variant | Trades | Available window | Full-window mean net R | Q1 2025 mean net R | Post-Q1 mean net R |
|---|---:|---|---:|---:|---:|
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 987 | 2024-12–2025-12 | -0.0122 | 0.2343 | -0.0957 |
| `ladder_a4b_entry_fsm_qgrid025` | 825 | 2024-12–2025-10 | -0.0315 | 0.1977 | -0.1299 |

## Control run status

The rule control executed 99,492 steps and opened 1057 positions. Ending equity was $89,977.27; the environment ended with done=False and truncated=True. Fill-level P&L ledger: [`p6_session_momentum_trade_ledger.csv`](p6_session_momentum_trade_ledger.csv).

## Reproducibility

- Campaign fingerprint: `b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4`.
- Analysis script SHA-256: `785010eebf429351edcbfa07088d37cd832269423d69f3b4d6a0b76bd4e550bb`.
- Inputs, data hashes, and control diagnostics: `p6_training_dynamics_control.json`.
- Monthly table: `p6_policy_monthly_dynamics.csv` and `p6_session_momentum_monthly_control.csv`.
