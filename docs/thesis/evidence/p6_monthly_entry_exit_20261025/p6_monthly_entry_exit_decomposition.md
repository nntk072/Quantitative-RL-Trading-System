# P6 2M Actual-Fill Monthly R and March–April Decomposition

This is a training-split-only replay analysis for the two completed 2M P6 arms, covering the configured 2024-12-30 through 2025-12-31 training interval. The tables show entry months and include the initial partial December 2024 month. It uses actual tick fills to report mid-quote gross R and raw bid/ask historical net R, with no stress and zero commission. The paired exit analysis freezes each actual entry and compares its actual outcome to an EMA21-exit replay with the same position size, stop, and paired latency. It does not use PPO inference, does not compound a counterfactual account, and does not read 2026 data.

## Execution manifest and fill audit

| Variant | Random latency | Effective extra tick slippage | Run manifest standalone key | Tick execution | Stop/target fill rows | Tick sourced | Raw bid/ask reconciliation errors |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ladder_a4a_entry_fsm_hidden_qgrid025` | 30.0 ms | 0.0 points (reanalysis manifest) | None | True | 799 | {'tick': 799} | 0 |
| `ladder_a4b_entry_fsm_qgrid025` | 30.0 ms | 0.0 points (reanalysis manifest) | None | True | 646 | {'tick': 646} | 0 |

The run manifest records configured model slippage of 5 points; the paired reanalysis manifest explicitly records `effective_tick_fill_slippage_points=0.0`. The 18 replay-relevant execution source files also match the training attempt hashes. The run manifest records randomized fill latency as 30 ms (with zero fixed delay). Every entry and completed close event was checked against an exact tick timestamp and executable quote side. Stop and target rows were also checked separately; all must be tick sourced. Raw executable bid/ask P&L is reconciled against the ledger’s historical net P&L before results are accepted. The table’s standalone run-manifest key is absent because that setting is recorded in the execution override manifest instead.

## Monthly results

### `ladder_a4a_entry_fsm_hidden_qgrid025`

| Entry month | N | Actual gross mid mean R (95% paired bootstrap CI) | Actual historical net bid/ask mean R | Mid-to-bid/ask drag R | EMA21 reference gross mean R | Actual − EMA21 mean gross R | Gross mid P&L sum | Historical net P&L sum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 12 | -0.5873 [-0.8921, -0.2012] | -0.6292 [-0.9409, -0.2364] | 0.0419 | -0.7610 | 0.1738 | $-3349.04 | $-3593.54 |
| 2025-01 | 81 | 0.3015 [-0.1045, 0.7824] | 0.2569 [-0.1477, 0.7346] | 0.0446 | 0.2979 | 0.0036 | $7742.28 | $6148.86 |
| 2025-02 | 88 | 0.3898 [-0.0312, 0.8766] | 0.3538 [-0.0667, 0.8412] | 0.0360 | 0.2619 | 0.1279 | $23566.08 | $21944.71 |
| 2025-03 | 100 | 0.1503 [-0.1209, 0.4462] | 0.1108 [-0.1610, 0.4069] | 0.0395 | 0.0194 | 0.1310 | $6401.43 | $4316.87 |
| 2025-04 | 90 | -0.0674 [-0.2864, 0.1711] | -0.0981 [-0.3166, 0.1395] | 0.0307 | -0.1083 | 0.0409 | $-1466.81 | $-2994.38 |
| 2025-05 | 73 | 0.2484 [-0.1780, 0.7787] | 0.2039 [-0.2209, 0.7312] | 0.0445 | -0.0541 | 0.3025 | $12469.18 | $10697.90 |
| 2025-06 | 104 | -0.0866 [-0.2964, 0.1298] | -0.1314 [-0.3425, 0.0852] | 0.0448 | -0.1451 | 0.0584 | $-10126.00 | $-12405.43 |
| 2025-07 | 45 | 0.0290 [-0.2336, 0.3278] | -0.0053 [-0.2691, 0.2939] | 0.0343 | -0.0990 | 0.1280 | $167.39 | $-555.09 |
| 2025-08 | 55 | -0.1773 [-0.4157, 0.0820] | -0.2145 [-0.4540, 0.0434] | 0.0373 | -0.0522 | -0.1251 | $-1915.60 | $-2825.84 |
| 2025-09 | 62 | -0.0347 [-0.2574, 0.2017] | -0.0667 [-0.2882, 0.1695] | 0.0320 | -0.0221 | -0.0126 | $-2712.72 | $-3755.96 |
| 2025-10 | 122 | -0.1743 [-0.3416, -0.0055] | -0.2057 [-0.3731, -0.0363] | 0.0314 | -0.1765 | 0.0022 | $-8816.17 | $-10613.25 |
| 2025-11 | 80 | -0.0086 [-0.2449, 0.2424] | -0.0361 [-0.2723, 0.2154] | 0.0275 | 0.0298 | -0.0384 | $-1840.25 | $-2830.17 |
| 2025-12 | 75 | -0.1655 [-0.3994, 0.0767] | -0.2107 [-0.4461, 0.0340] | 0.0451 | -0.2887 | 0.1232 | $-4183.07 | $-5689.00 |

March → April actual gross expectancy changed by **-0.2177 R/trade** (95% paired month-stratified bootstrap CI [-0.5837, 0.1429]). The decomposition assigns **-0.1276 R** to the change in EMA21-reference outcomes for that month’s frozen entries (CI [-0.4610, 0.2243]) and **-0.0901 R** to the month-to-month change in actual-minus-EMA21 outcomes (CI [-0.3474, 0.1406]). March N=100; April N=90. The point estimates add exactly.

### `ladder_a4b_entry_fsm_qgrid025`

| Entry month | N | Actual gross mid mean R (95% paired bootstrap CI) | Actual historical net bid/ask mean R | Mid-to-bid/ask drag R | EMA21 reference gross mean R | Actual − EMA21 mean gross R | Gross mid P&L sum | Historical net P&L sum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 12 | -0.5874 [-0.8921, -0.2015] | -0.6293 [-0.9409, -0.2367] | 0.0419 | -0.7610 | 0.1737 | $-3209.19 | $-3443.83 |
| 2025-01 | 83 | 0.2744 [-0.1244, 0.7592] | 0.2306 [-0.1683, 0.7141] | 0.0438 | 0.2857 | -0.0113 | $7078.67 | $5523.50 |
| 2025-02 | 83 | 0.3296 [-0.0599, 0.8062] | 0.2958 [-0.0939, 0.7693] | 0.0339 | 0.2248 | 0.1049 | $19922.48 | $18470.04 |
| 2025-03 | 100 | 0.1305 [-0.1268, 0.4147] | 0.0891 [-0.1679, 0.3745] | 0.0414 | 0.0399 | 0.0906 | $5550.07 | $3511.45 |
| 2025-04 | 104 | -0.0933 [-0.2892, 0.1112] | -0.1251 [-0.3213, 0.0788] | 0.0318 | -0.1197 | 0.0264 | $-5075.52 | $-6910.39 |
| 2025-05 | 67 | -0.0155 [-0.3322, 0.3576] | -0.0563 [-0.3729, 0.3152] | 0.0408 | -0.1043 | 0.0888 | $1850.23 | $472.81 |
| 2025-06 | 102 | -0.0889 [-0.3217, 0.1645] | -0.1334 [-0.3673, 0.1226] | 0.0444 | -0.1702 | 0.0813 | $-8274.25 | $-10331.77 |
| 2025-07 | 47 | 0.0299 [-0.2147, 0.3044] | -0.0026 [-0.2493, 0.2726] | 0.0325 | -0.1255 | 0.1554 | $574.96 | $-58.40 |
| 2025-08 | 52 | -0.1529 [-0.4099, 0.1244] | -0.1907 [-0.4486, 0.0870] | 0.0378 | -0.0160 | -0.1369 | $-1920.61 | $-2670.93 |
| 2025-09 | 64 | -0.0968 [-0.3028, 0.1183] | -0.1285 [-0.3333, 0.0861] | 0.0317 | -0.1158 | 0.0190 | $-3923.22 | $-4829.51 |
| 2025-10 | 111 | -0.1697 [-0.3330, 0.0005] | -0.2021 [-0.3660, -0.0321] | 0.0324 | -0.1875 | 0.0178 | $-8304.81 | $-9789.02 |

March → April actual gross expectancy changed by **-0.2238 R/trade** (95% paired month-stratified bootstrap CI [-0.5656, 0.1118]). The decomposition assigns **-0.1595 R** to the change in EMA21-reference outcomes for that month’s frozen entries (CI [-0.4654, 0.1505]) and **-0.0642 R** to the month-to-month change in actual-minus-EMA21 outcomes (CI [-0.2843, 0.1457]). March N=100; April N=104. The point estimates add exactly.

The A4B account path terminated after its October 2025 hard-floor failure; its November and December rows are absent because there were no later training trades, not because those months had zero expectancy. A4A continued through December.

## Interpretation boundary

The EMA21 replay is a conditional reference, not a causal intervention and not a full portfolio counterfactual. The entry component means ‘how the same frozen entries performed under this common EMA21 exit rule’; the exit component is the paired difference from actual outcomes to that reference. This separates relative exit contribution from the market opportunities represented by monthly entry cohorts, but cannot prove that entry timing alone caused the market shift. R is normalized by each actual trade’s initial modeled stop risk. Monthly sums are un-compounded.

## Reproducibility

- Campaign fingerprint: `b37580606ca374326bce7207fb7eef118cede36cf0eaad25d37be9465bb4e1e4`.
- Analysis script SHA-256: `7d3d0b8a0cc9f4d061c474b03220df3478b94cdf99ee4f246aa0a492104c37cc`.
- Bootstrap: 10,000 resamples, seed 20261025.
- Per-entry matched data: `ladder_*_paired_trades.csv`.
- Complete input, manifest and source hashes: `p6_monthly_entry_exit_decomposition.json`.
- Script: [`scripts/research/thesis/p6_monthly_entry_exit_decomposition.py`](../../../scripts/research/thesis/p6_monthly_entry_exit_decomposition.py).
