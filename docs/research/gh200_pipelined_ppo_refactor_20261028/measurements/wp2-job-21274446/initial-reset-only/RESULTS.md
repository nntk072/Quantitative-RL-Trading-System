# WP2 exact market-row reuse inference A/B

**Job:** `21274446` on `gpuarm1.int.triton.aalto.fi`; two GH200s, one inference arm per GPU.
**Scope:** fresh seed-42 policy initialization and observations from the pinned training bundle; no PPO updates or trade replay.
**Source commit:** `248d5b1eeeb5ae0a7817d049607e8eb8d99e28a6`
**Bundle manifest SHA-256:** `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`
**Resolved config SHA-256:** `80e2dfc54460bdcce554e86d5b467011dc8555591945825064c454b7ea962ddd`
**Policy state SHA-256:** `d7db4a2d263a808c21f304648c6219f7878fe5404590d503c56da268ce71f1f8`

## Market reuse and parity

- Exact duplicate market rows: **1 / 64**.
- Exact market reuse factor: **64.00x**.
- Unique account rows: **1 / 64**.
- Same complete observation batch in both arms: **True**.
- Same seed, bundle, resolved config, initial policy weights, and source: **True**.
- Feature, masked thesis logits/probabilities, deterministic actions, values, forward/evaluated log probabilities, and entropy all meet their listed tolerances: **True**.

| Output | Maximum absolute difference | Tolerance |
|---|---:|---:|
| deterministic_action | 5.774e-08 | 1.0e-05 |
| entropy | 0.000e+00 | 1.0e-05 |
| features | 1.242e-04 | 2.0e-04 |
| forward_log_prob | 0.000e+00 | 1.0e-05 |
| log_prob | 0.000e+00 | 1.0e-05 |
| thesis_logits | 0.000e+00 | 1.0e-05 |
| thesis_probs | 0.000e+00 | 1.0e-05 |
| value | 5.582e-05 | 1.0e-04 |

## Full-policy latency

| Path | p50 ms / 64-env batch | p95 ms / 64-env batch |
|---|---:|---:|
| Full MTF encoding | 10.713 | 11.610 |
| Group exact duplicate market rows | 11.192 | 11.732 |

Grouped p50 speedup: **0.957x**.

## Limits

This measures repeated full-policy inference on one fixed 64-environment observation batch. It excludes the CPU work to discover duplicate rows, simulator stepping, IPC, PPO updates, callbacks, checkpointing, and year replay. The policy is freshly initialized for a numerical/path-parity and latency probe, not a trained checkpoint. These timings alone do not justify an integrated collector or a training-quality claim.
