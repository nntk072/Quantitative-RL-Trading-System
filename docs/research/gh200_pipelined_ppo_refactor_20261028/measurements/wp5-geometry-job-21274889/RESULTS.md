# WP5 PPO Epoch Geometry Throughput Screen

- Allocation: `21274889`, one GH200 on `gpuarm1`.
- Matched seeds: 42, 43, 44.
- 64 environments, 256 steps per environment, 4,096 minibatch, 81,920 total transitions per run.
- Each run used two warmup rollouts and three measured rollouts (49,152 measured transitions).
- The only resolved-config change from the 15-epoch control was `ppo.n_epochs`.
- Bundle manifest SHA-256 for all runs: `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`.
- Throughput includes rollout collection and PPO updates; two warmup rollouts are excluded from the rate.

## Results

| PPO epochs | Seed 42 | Seed 43 | Seed 44 | Mean ± sample SD steps/s | Paired gain vs 15 epochs |
|---:|---:|---:|---:|---:|---:|
| 15 | 1,165.14 | 1,145.50 | 1,156.07 | 1,155.57 ± 9.83 | Reference |
| 10 | 1,337.90 | 1,349.39 | 1,378.40 | 1,355.23 ± 20.87 | +17.29% ± 2.25 pp |
| 5 | 1,606.85 | 1,616.78 | 1,655.91 | 1,626.52 ± 25.94 | +40.76% ± 2.68 pp |

Mean measured PPO update time per three-rollout core was 17.73 seconds at 15 epochs, 11.98 seconds at 10, and 6.23 seconds at 5. The runs execute fewer optimizer steps by design; they are changed learning protocols, not equivalent implementations of the 15-epoch policy.

## Decision and limitation

This is a throughput-only screen. The benchmark does not save trained checkpoints or evaluate trading outcomes, survival, sample efficiency, or policy quality. It cannot establish that either reduced-epoch variant is acceptable for thesis training. Keep the existing 15-epoch configuration as the reference. Any 10- or 5-epoch use needs a separately declared training protocol and a matched learning-quality evaluation on development data before selection; do not tune on the exposed 2026 report period.

Raw per-seed JSON and logs are in this directory. The 15-epoch control files are in `../compact-obs-job-21274889/`.
