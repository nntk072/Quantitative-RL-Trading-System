# GH200 Maximum-Throughput Redesign: Results and Handoff

| Field | Value |
|---|---|
| Date | 2026-10-28 |
| Implementation lineage | `codex/gh200-max-fps`, based on `3fbbb74fdbe581807df38c1feaab7307839506f5` |
| Hardware | One NVIDIA GH200 144G on `gpuarm1`, ARM64, 48 allocated CPUs, 256 GiB host RAM |
| Software | Python 3.12.15, PyTorch 2.14.0+cu130, CUDA 13.0, driver 580.173.02 |
| Data | Shared bundle manifest SHA-256 `d85e0dc8fa241c66d4d727dd4be5d463fc58dbbbd53a43fd00d75100387b052e` |
| Training config | `config/research/thesis_mtf_shared_tcn_2m.yaml`, resolved config SHA-256 `7d15f4492769de29347ca5af0dbd888bc5cd61ad984f0932426cc73491a9a216` |

Every recorded profile uses seed 42. These are PPO-core throughput profiles, without production callbacks, checkpoint selection, or train/test replay.

## Decision

The useful gain came from increasing vector width and learner batch geometry, not from the tested small code changes. The fixed-aggregate 64-env screen measured 552.7 transitions/s. The separate 64-env high-throughput setup measured roughly 0.91–0.98k transitions/s across runs, with 15 PPO epochs retained. The high-throughput setup changes PPO rollout and minibatch geometry, so it is a new experimental training line, not a matched C/D run or the same learning trajectory.

The combined hot-path code prototype did not show a consistent speed gain at the 8-env reference geometry. At 64-env high geometry, its apparent gain over the stable baseline repeats was about 1.4%, which is too small and inconsistent across geometries to justify maintaining the code changes. That prototype passed its focused tests, but it was reverted. The main checkout and C/D source lineage remain unchanged.

## Measurements

Core rate is warmup-excluded transitions divided by measured rollout plus PPO update time. The 65,536-step screens discard two complete rollouts and measure 61,440 transitions. The high geometry screen measures 229,376 of its 262,144 transitions after two warmup rollouts.

| Profile | Env / rollout / batch / epochs | Core transitions/s | Rollout s/s | Update seconds | Mean CPU cores | Host RAM peak | GPU memory peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| E8 reference, 3 repeats | 8 / 2,048 / 512 / 15 | 222.3 ± 4.8 | 305 | 75.0 | 1.48 | 4.9 GiB | 1.76 GiB |
| E16 fixed aggregate | 16 / 2,048 / 512 / 15 | 314.1 | 528 | 79.2 | 1.86 | 5.8 GiB | 1.76 GiB |
| E32 fixed aggregate | 32 / 2,048 / 512 / 15 | 427.6 | 966 | 80.0 | 2.21 | 7.6 GiB | 1.77 GiB |
| E64 fixed, separate workers | 64 / 2,048 / 512 / 15 | 552.7 | 1,798 | 77.0 | 2.67 | 11.2 GiB | 1.79 GiB |
| E64 fixed, 16 worker shards | 64 / 2,048 / 512 / 15 | 521.2 | 1,470 | 76.1 | 2.36 | 6.5 GiB | 1.79 GiB |
| E64 high geometry | 64 / 16,384 / 4,096 / 15 | 910.8 in the initial screen; see matched repeats below | 1,390 | 86.8 | 3.41 | 7.7 GiB | 13.42 GiB |

The E64 fixed-aggregate run reaches the plan's ≥500 transitions/s screening target while preserving the 2,048 aggregate rollout and batch 512. The high-geometry profile increases aggregate rollout eightfold and batch size eightfold, while retaining 15 epochs. It runs four times as many transitions as the small screen and performs 960 optimizer steps instead of 1,920 per 65,536 transitions. This changes optimization dynamics.

### High-geometry code A/B

All runs used 64 envs, 16 shards, 16,384 aggregate rollout, batch 4,096, 15 epochs, seed 42, and the same bundle. Baseline runs used the unmodified source at the recorded commit. Candidate runs used the temporary patch identified by the SHA-256 in `measurements/hotpath-manifest.txt`.

| Source | Core transitions/s, each repeat | Mean ± sample SD |
|---|---:|---:|
| Baseline | 910.8, 962.2, 960.4 | 944.5 ± 29.4 |
| Candidate patch | 971.0, 980.7, 971.3 | 974.3 ± 5.6 |

The first baseline run is materially lower than the two later baseline repeats. Comparing the later baseline repeats to the candidate mean yields about +1.4%; comparing all baseline runs yields +3.2%. The 8-env matched repeats instead moved from 222.3 ± 4.8 to 217.2 ± 5.7 transitions/s. There is no reliable cross-geometry end-to-end gain, so the candidate code patch was rejected and reverted. The benchmark JSONs preserve both sides of the comparison.

## Bottleneck evidence and package decisions

- **Rollout collection dominates at E8.** Across the three reference runs, measured rollout/framework time averaged 201.5 seconds, versus 75.0 seconds for PPO updates. Increasing env count improves rollout throughput much more than reducing update time.
- **Environment step is not the dominant wall-time target.** Instrumented E8 measured 195.7 aggregate environment-step CPU seconds and a 25.8-second wall lower bound over 275.2 seconds of measured PPO-core time (9.4%). Even eliminating that lower-bound work cannot explain a multi-fold speedup. WP5 market-window caching and WP6 environment rewrites are no-go for this plan; preserve CPU simulator semantics.
- **Worker sharding trades speed for RAM.** Sixteen shards use 6.5 GiB rather than 11.2 GiB for 64 subprocesses, at 521 versus 553 transitions/s. Both fit comfortably in the measured allocation; the higher-throughput separate-worker layout is the current fixed-aggregate winner.
- **CUDA compilation is blocked by the node toolchain.** The allocated ARM node has no `cc`, `gcc`, `clang`, `nvcc`, or `ptxas`. No compiler or CUDA Graph installation was attempted. WP3 is deferred pending a supported compiler environment.
- **Rollout-buffer/device-sync prototype was rejected.** Fusing value and log-probability copies, device-resident fixed action tensors, and asynchronous mask validation passed focused tests (15 passed), but the combined patch did not improve the 8-env reference and its high-geometry advantage was small. The implementation and tests were reverted.
- **WP4 large GPU rollout storage is no-go for now.** The modest sync prototype did not establish a repeatable win; a GPU-backed rollout rewrite would add considerable compatibility risk without a measured bottleneck case.
- **WP7 end-to-end evaluation was not benchmarked.** These profiles omit dashboard callbacks, checkpoint ranking/saving, full 2025 replay and 2026 report-only replay. A core-only 2M extrapolation is about 2.5 hours at the E8 reference, 1.0 hour at E64 fixed aggregate, and roughly 35 minutes at the high-geometry baseline rate. These are arithmetic extrapolations, not full-run ETAs. The original plan's evaluation allowances (0.55 h dashboards and 1.06 h final replay) were not remeasured here; adding them plus 25% reserve to the high-geometry core estimate gives about 2.7 h, but that remains a planning scenario rather than measured end-to-end time.

## Training and policy sanity

The high-geometry profile completed 262,144 PPO environment steps with finite PPO diagnostics. In its final logger window, approximate KL was 0.00664, explained variance 0.667, entropy loss -6.96, and value loss 2.85. This is a bounded optimization-stability check only. The profiler did not save a checkpoint or measure thesis-choice diversity, invalid-selection counts, trade behavior, account survival, train-calendar equity, or test-period performance. No policy-quality, sustainability, or economic-performance claim follows from these numbers.

No 2M campaign was launched. The new config is only prepared for a separately authorized 2M experiment. The existing C/D successor `21267207` remains held with its `afterany:21264865` dependency intact. Do not release it until the redesign work is committed and pushed; then it remains the previously approved C/D experiment on its frozen baseline, not this high-geometry E variant.

## Reproduction artifacts

- Original plan with the later approval recorded: [`GH200_MAX_FPS_ARCHITECTURE_REDESIGN_PLAN_2026-10-28.md`](../GH200_MAX_FPS_ARCHITECTURE_REDESIGN_PLAN_2026-10-28.md)
- Separate high-geometry config: [`thesis_mtf_shared_tcn_2m_high_throughput.yaml`](../../../config/research/thesis_mtf_shared_tcn_2m_high_throughput.yaml)
- Baseline, geometry, A/B JSON measurements and toolchain evidence: [`measurements/`](measurements/)
- Checksum list: [`measurements/SHA256SUMS`](measurements/SHA256SUMS)
