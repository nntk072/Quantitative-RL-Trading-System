# Compact Observation Transport A/B

- Benchmark directory: `docs/research/gh200_pipelined_ppo_refactor_20261028/measurements/compact-obs-job-21274889`
- Validation smoke with per-observation market hashes: PASS
- Paired seeds: 42, 43, 44; same frozen bundle, resolved config, and PPO geometry.
- Throughput includes rollout collection and PPO updates; two rollout warmups are excluded.
- Each timed run requested 81,920 transitions (two warmups plus three measured rollouts).
- Compact transport sends the absolute source row and per-environment account vector; the parent reconstructs other fields from the same immutable bundle.

## PPO-core throughput

| Seed | Stock transitions/s | Compact transitions/s | Paired change |
|---:|---:|---:|---:|
| 42 | 1165.14 | 1082.37 | -7.10% |
| 43 | 1145.50 | 1099.10 | -4.05% |
| 44 | 1156.07 | 1100.61 | -4.80% |
| Mean ± sample SD | 1155.57 ± 9.83 | 1094.03 ± 10.12 | -5.32% ± 1.59 pp |

## Parent receive-buffer bytes

| Seed | Stock IPC bytes | Compact IPC bytes | Reduction |
|---:|---:|---:|---:|
| 42 | 7,870,042,515 | 155,431,637 | 98.03% |
| 43 | 7,868,907,754 | 155,407,559 | 98.03% |
| 44 | 7,869,259,134 | 155,486,005 | 98.02% |
| Mean ± sample SD | 7,869,403,134 ± 580,924 | 155,441,734 ± 40,186 | 98.02% ± 0.00 pp |

## Decision

- >=20% repeatable PPO-core speedup gate: NOT MET.
- A reduction in IPC bytes alone does not justify integration; use the measured PPO-core result and correctness gate.
- This prototype reconstructs observations from the same market bundle in the parent. It is not production training behavior and is not a GPU-native simulator.
- Detailed IPC serialization CPU and device-link bandwidth are not measured by the parent receive-buffer counter.
