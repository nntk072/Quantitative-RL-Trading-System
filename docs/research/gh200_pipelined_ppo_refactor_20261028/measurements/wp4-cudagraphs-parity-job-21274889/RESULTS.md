# WP4 CUDA Graph Policy-Forward A/B

- Allocation: `21274889`, one GH200 on `gpuarm1`.
- Matched seeds: 42, 43, 44.
- Resolved config SHA-256: `64c825188b83151c0a8f571298a94c8c1d5a373bc9668e7b7adea407e18cc632`.
- Shared bundle manifest SHA-256: `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e`.
- Geometry for every run: 64 environments, 256 steps per environment, 4,096 minibatch, 15 PPO epochs, 81,920 total transitions (two warmups and three measured rollouts).
- Core throughput includes rollout collection and PPO updates. Compile warmup is reported separately.

## Results

| Seed | Eager PPO core steps/s | CUDA Graph PPO core steps/s | Paired change |
|---:|---:|---:|---:|
| 42 | 1,165.14 | 1,481.81 | +27.18% |
| 43 | 1,145.50 | 1,482.82 | +29.45% |
| 44 | 1,156.07 | 1,482.83 | +28.26% |
| Mean ± sample SD | 1,155.57 ± 9.83 | 1,482.49 ± 0.58 | +28.30% ± 1.13 pp |

The compile warmup took 10.91 seconds on average. It is a one-time per-model cost; it is excluded from the reported PPO-core rate. The measured speedup clears the plan's 20% throughput threshold in all three paired repeats. This is a core-runtime estimate, not a full training-plus-evaluation campaign time.

## Correctness and limits

The final runs compare eager and compiled policy outputs in evaluation mode at the same fixed batch shapes. Actions, values, rollout log probabilities, evaluated values and log probabilities matched exactly in all three seeds. The maximum entropy difference was `4.7684e-6`; the configured comparison tolerance was `1e-5` absolute and relative. Existing thesis-mask distribution tests continue to check invalid categories receive exactly zero probability.

Torch Dynamo reports a graph break at the current tensor-to-Python mask-validity check in `learning/rl/hybrid.py`. The CUDA Graph backend still completed the full benchmark and preserved the tested outputs. The initial Inductor backend remains unavailable on this node because no C++ compiler is installed; no toolchain was installed. An earlier parity attempt compared two policy calls with dropout active and failed; the harness now compares deterministic evaluation-mode outputs and separately warms the training-mode graph before measuring.

The optimization is implemented in the throughput harness only. Production campaign construction, checkpoint save/load under a compiled policy, and complete campaign makespan have not been validated. Therefore the result establishes a promising exact-forward optimization candidate, not authorization to silently change existing campaign behavior.

Raw matched output is in `seed42.json` through `seed44.json`. The earlier one-off without the parity check is retained separately in `../wp4-cudagraphs-job-21274889/` and is not included in the paired summary.
