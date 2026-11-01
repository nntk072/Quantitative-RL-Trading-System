# Fixed-entry exit-only shadow results

This is a conditional trade-level analysis of the archived 2025 v2 entries. It is not a new strategy backtest, does not compound a shadow equity curve, and does not use PPO or the 2026 split.

## Protocol and input boundary

- Frozen entries: 1,356; eligibility: 1,062; ineligible: 294; unresolved: 0.
- Paired primary rows: 1,062; EMA control fill-parity rows: 1,355/1,356.
- Archived source commit: `cbf7825170dee7f68ad578a19023e0847b11393f`; called execution methods match it: `True`.
- Audited source differences outside the replay path: factory sizing-cap resolution is outside replay because quantity is frozen; new percentage guardrail fields are inactive under the archived fixed-USD mode; episode reward limit kwargs are not called.
- 2025-only ticks: 56,245,046, ending `2025-12-31T20:49:59.919000+00:00`. Features were read with a pre-2026 cutoff and aligned exactly to training bars.
- Latency is paired by entry: the first draw reuses that entry's archived v2 exit latency; later event draws are keyed by entry ID and event order.
- Historical tick fills use bid/ask with the archived effective tick slippage of zero and zero commission. Stress adds 5 adverse points at entry and each exit fill, matching the configured slippage amount as a one-sided stress.
- MAE/MFE use executable liquidation-side ticks from each actual fill through that arm's own final exit. The initial USD stop risk is fixed across both arms.

## Paired result

| Metric | Result |
|---|---:|
| Mean ΔR, structural − EMA | 0.0070 |
| Median ΔR | 0.0000 |
| Standard deviation | 0.7942 |
| 95% paired bootstrap CI for mean | [-0.0416, 0.0528] |
| Structural wins / EMA wins / ties | 197 / 172 / 693 |
| Mean ΔR, gross | 0.0069 |
| Mean ΔR, cost stress | 0.0070 |

## Exit outcomes

| Arm | Exit reason | Count | Mean R | Median R |
|---|---|---:|---:|---:|
| ema | ema_21_exit | 186 | 0.9647 | 0.9575 |
| ema | session_end | 16 | 0.8274 | 0.4508 |
| ema | structure_sl | 1154 | -0.1754 | -0.0815 |
| structural | session_end | 10 | 0.7400 | 0.4134 |
| structural | structure_sl | 928 | -0.2078 | -0.1010 |
| structural | structure_tp3 | 124 | 1.4697 | 1.3249 |

## Monthly conditional result

Monthly P&L is the sum of frozen trade outcomes, not a compounded account equity curve.

| Entry month | Frozen N | EMA W/L/BE | EMA win rate | Mean EMA R | EMA net P&L, all ($) | Paired N | EMA net P&L, paired ($) | Structural net P&L ($) | Mean ΔR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 14 | 6/7/1 | 42.9% | -0.314 | -3719.72 | 14 | -3719.72 | -2259.76 | 0.1265 |
| 2025-01 | 129 | 53/76/0 | 41.1% | 0.076 | 7929.04 | 100 | 9758.18 | 5633.85 | -0.0487 |
| 2025-02 | 122 | 55/67/0 | 45.1% | 0.063 | 6532.71 | 97 | 6149.23 | -2912.55 | -0.1016 |
| 2025-03 | 149 | 73/76/0 | 49.0% | 0.223 | 32702.36 | 122 | 30232.69 | 26917.93 | -0.0253 |
| 2025-04 | 105 | 36/69/0 | 34.3% | -0.191 | -20098.67 | 90 | -18926.18 | -7362.95 | 0.1285 |
| 2025-05 | 107 | 44/63/0 | 41.1% | -0.038 | -4255.83 | 88 | -5890.49 | -4801.86 | 0.0116 |
| 2025-06 | 121 | 52/69/0 | 43.0% | 0.047 | 5335.32 | 90 | 4082.15 | -3010.01 | -0.0811 |
| 2025-07 | 132 | 50/82/0 | 37.9% | -0.033 | -4325.01 | 102 | -5421.50 | 6454.18 | 0.1164 |
| 2025-08 | 117 | 42/75/0 | 35.9% | -0.023 | -3357.30 | 90 | -1771.49 | -3719.58 | -0.0276 |
| 2025-09 | 149 | 44/104/1 | 29.5% | -0.083 | -12009.05 | 103 | -9412.26 | -11567.21 | -0.0224 |
| 2025-10 | 173 | 67/106/0 | 38.7% | -0.061 | -9312.31 | 134 | -10735.67 | -676.79 | 0.0854 |
| 2025-11 | 38 | 12/26/0 | 31.6% | -0.198 | -6042.70 | 32 | -6167.09 | -6452.76 | -0.0111 |

## Interpretation limits

The paired estimate answers whether structural exits changed outcomes for the same historical v2 entries. The near-zero overall ΔR and interval spanning zero mean this exit change does not explain the March–April peak and later decline. The monthly EMA control shifts from a 49.0% win rate and +0.223 mean R in March to a 34.3% win rate and −0.191 mean R in April; September through November remain mostly losing cohorts. Frozen quantities average about $874–$1,000 initial risk per trade, so the decline is not explained by smaller position risk. This identifies weaker later trade outcomes, but it does not identify whether entry quality, policy learning, or market regime caused them.

The full EMA control must pass its documented exact-fill gate before the structural result is treated as scientifically interpretable. The one original account-level max-drawdown close is replayed without account-path truncation; its natural exit may differ and is reported as a known boundary exception.

## Reproducibility

- Bootstrap: 10,000 paired resamples, seed 20261024.
- Deterministic repeat: `True`.
- All file identities and output hashes: [`provenance.json`](provenance.json).
- Trade ledger: [`paired_trades.csv`](paired_trades.csv); fill and management events: [`shadow_events.jsonl`](shadow_events.jsonl).
- Plot: [`paired_delta_r.png`](paired_delta_r.png).
