# WP2 exact market-row reuse inference A/B

**Job:** `21274446` on `gpuarm1.int.triton.aalto.fi`; two GH200s, one inference arm per GPU.
**Scope:** fresh seed-42 policy initialization and observations from the pinned training bundle; no PPO updates or historical replay.
**Source commit:** `248d5b1eeeb5ae0a7817d049607e8eb8d99e28a6`
**Bundle manifest SHA-256:** `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`
**Resolved config SHA-256:** `80e2dfc54460bdcce554e86d5b467011dc8555591945825064c454b7ea962ddd`
**Policy state SHA-256:** `d7db4a2d263a808c21f304648c6219f7878fe5404590d503c56da268ce71f1f8`

## Market reuse and parity

- Exact duplicate market rows: **1 / 64**.
- Exact market reuse factor: **64.00x**.
- Across 128 vector steps, market reuse was p50 **64.00x**, p95 **64.00x**.
- Across the same steps, account unique-row count was p50 **62**, p95 **64** of 64 environments.
- Unique account rows: **1 / 64**.
- Same complete observation batch in both arms: **True**.
- Same evolving rollout observations in both arms: **True**.
- Same seed, bundle, resolved config, initial policy weights, and source: **True**.
- Feature, masked thesis logits/probabilities, deterministic actions, values, forward/evaluated log probabilities, and entropy all meet their listed tolerances: **True**.

| Output | Max absolute difference | Max relative difference | Absolute tolerance |
|---|---:|---:|---:|
| deterministic_action | 3.235e-07 | 8.530e-03 | 1.0e-05 |
| entropy | 9.537e-07 | 1.357e-07 | 1.0e-05 |
| features | 2.278e-04 | 2.115e-02 | 3.0e-04 |
| forward_log_prob | 9.537e-07 | 1.973e-07 | 1.0e-05 |
| log_prob | 9.537e-07 | 1.973e-07 | 1.0e-05 |
| thesis_logits | 6.557e-07 | 9.517e-07 | 1.0e-05 |
| thesis_probs | 3.278e-07 | 6.584e-07 | 1.0e-05 |
| value | 9.695e-05 | 6.759e-03 | 1.5e-04 |

All outputs also use relative tolerance `rtol=1.0e-05`.

## Full-policy latency

| Path | p50 ms / 64-env batch | p95 ms / 64-env batch |
|---|---:|---:|
| Full MTF encoding | 10.842 | 11.476 |
| Group exact duplicate market rows | 10.547 | 10.914 |

Grouped p50 speedup: **1.028x**.

## Limits

This advances a freshly initialized random policy stochastically through 128 simulator steps per environment to observe market reuse and account divergence; it does not train and is not a trained-checkpoint evaluation. Latency is measured on the initial, midpoint, end, and terminal observation batches. It excludes the CPU work to discover duplicate rows, simulator stepping, IPC, PPO updates, callbacks, checkpointing, and year replay. These timings alone do not justify an integrated collector or a training-quality claim.
