# Variant C/D runtime readiness update

**Updated:** 2026-10-28, Europe/Helsinki  
**Scope:** measured runtime diagnosis and a pre-run estimate for the matched C/D
2M comparison. This is not the 2M result and does not authorize starting it.

## Decision state

The 100k C/D pilots and their full 2025 training-split replays are complete.
Both policies traded, but both failed the configured account-survival gate in
the replay. The policies and configs remain a matched experimental pair; no
architecture or action-schema changes are proposed here. A fresh 2M C/D run
remains gated on the user's explicit acceptance.

## Existing 100k checkpoint train and report-only replay

Attempt 35 replayed both unselected 100k checkpoints over all 99,492 training
decision bars and all 79,069 available 2026 report-only bars. It used
stochastic actions with seed 42. This is an exploratory pilot, not the matched
2M result; the 2026 interval is exposed and cannot support a fresh holdout
claim.

| Arm / split | Trades | Net return | PF | Win rate | Max DD | Expectancy/trade | Risk breaches | Stop time |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| C / 2025 train | 337 | −10.14% | 0.795 | 45.10% | 11.22% | −$30.08 | 5 | Jan 17, 2025 |
| C / 2026 report-only | 284 | −10.23% | 0.745 | 44.72% | 13.73% | −$36.01 | 2 | Jan 20, 2026 |
| D / 2025 train | 1,016 | −9.96% | 0.928 | 43.70% | 20.89% | −$9.80 | 8 | Feb 26, 2025 |
| D / 2026 report-only | 336 | −10.04% | 0.810 | 39.29% | 15.40% | −$29.87 | 4 | Jan 22, 2026 |

Any TP timeframe is valid per the user's clarified rule. The report field for
lower-timeframe TP references is informational only, not a violation gate; the
attempt-35 replays happened to record zero such references.

Both arms traded and stopped near the $90,000 account floor in each split.
Across the four split replays, selected thesis choices covered four idea
classes and nine setup timeframes; invalid selections and structural SL/TP
violations were exactly zero. Mean thesis entropy was 0.562/0.551 nats for C
(train/report-only) and 0.582/0.607 for D. NO_TRADE rates were 73.7%/74.8% for
C and 55.0%/54.2% for D; conditional NO_TRADE rates when a trade thesis was
eligible were 63.0%/65.3% for C and 36.7%/37.0% for D. D's execution
conditioning was active in both replays; C's was inactive as designed. These
diagnostics show the policy selected multiple ideas and timeframes and did not
collapse to NO_TRADE, but neither arm survived the full split or produced
positive net returns. D's code-level dependence is also covered by
`test_thesis_conditioned_distribution_masks_and_conditions_execution`: for a
fixed market latent, selecting thesis IDs 5 versus 31 changes execution
outputs while leaving thesis logits unchanged. That verifies the conditional
path, not its economic value.

The attempt-35 ledger, report tables, and plots are preserved at
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt35/{C,D}/report/`.
Each arm has separate `training/equity.png` and `testing/equity.png`; the test
figures are report-only exploratory artifacts.

## Runtime measurements

The most recent matched production-path profile is preserved in
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt39/`. It used the same
training bundle manifest (`d85e0dc8…87b052e`), seed 42, eight environments,
100,352 actual PPO steps, `sharded_bundle` with four shards, and disabled the
dashboard replay while retaining one deterministic best-prefix evaluation.
The PPO policy configs were unchanged between C and D. These profiles were
made from repository SHA `bb4cb6706d5d4d75a69c0a86b18a343c59a9e10a` with an
uncommitted source patch (`381081ec…d53156`); they are preserved measurements,
not a clean-tree rerun at the current `main` commit.

| Measure | C | D |
|---|---:|---:|
| Training wall time | 1,180.5 s | 1,155.9 s |
| PPO learn time | 1,175.6 s | 1,151.1 s |
| Measured throughput | 85.36 steps/s | 87.18 steps/s |
| Rollout collection, including best-prefix replay | 881.5 s | 853.6 s |
| Best-prefix replay within collection | 221.2 s | 212.2 s |
| PPO update time | 293.2 s | 296.7 s |
| Preparation + model setup | 41.6 s | 40.2 s |
| Peak cgroup RAM | 32.5 GiB | 33.0 GiB |
| Mean GPU utilization | 10.4% | 10.9% |
| Mean GPU memory | 1.85 GiB | 1.85 GiB |
| Mean allocated CPU use | 1.14 cores | 1.09 cores |

An earlier SubprocVecEnv run at the same 100k size took 1,171.6 seconds for C
and 1,157.5 seconds for D. The sharded bundle run changed those wall times by
only +0.34% for C and −0.56% for D. That backend change did not deliver a
meaningful throughput gain.

The profile attributes 56–57% of PPO learn time to rollout collection after
removing the single best-prefix evaluation, and about 25% to PPO updates. The
best-prefix replay itself costs 3.5 minutes. GPU utilization and memory are
low, and host RAM has substantial observed headroom. Average CPU use is also
low relative to the allocation. Per-process samples show the trainer Python
process averaging about 90% of one CPU core, while several sampled environment
workers average roughly 5–9% each. This places the strongest measured
constraint in the single-thread trainer/coordination path, rather than showing
all environment workers saturated. The samples do not separate Python action
inference, observation stacking, IPC, and metric synchronization; a stack
profile would be needed to name the hot function. Changing the encoder is
outside this matched C/D comparison.

A separate core-only probe in `attempt41/core/` ran three warmup-excluded
20,480-step repeats per arm with `SubprocVecEnv`, the same eight-env rollout
geometry, and production callbacks disabled. Mean throughput was **88.56
steps/s for C (sample SD 1.96)** and **84.65 steps/s for D (sample SD 3.75)**;
D was 4.4% slower in this short probe. Its source was commit
`9cd8bcad97398a4781c6c9f10946d0b3edc97f99` with a dirty working tree. In the
fuller production-path measurements, D was 2.9% slower in the three earlier
Subproc runs and 2.1% faster in the later sharded-bundle profile. These small,
path-dependent differences do not support a claim that D is dramatically
slower. They also do not rule out a modest policy-inference cost; the isolated
actor microbenchmark in the planning brief measured D's actor calls about
14–15% slower, but that was not a full training measurement.

### Current-source repeat and D hot-function profile

Attempt43 repeated the same 20,480-step, eight-env PPO-core measurement three
times per arm on clean current `main` SHA
`44ec01129c0276abdce6a228f8bd20b693d7f721`, with the same bundle and seed 42.
Each rate excludes the first two warm-up rollouts. Production callbacks were
disabled; these are engineering throughput measurements, not policy results.

| Arm | Repeat 1 | Repeat 2 | Repeat 3 | Mean steps/s | Sample SD |
|---|---:|---:|---:|---:|---:|
| C | 87.56 | 85.82 | 90.82 | 88.07 | 2.54 |
| D | 81.17 | 83.63 | 80.56 | 81.79 | 1.57 |

D was 7.1% slower than C in this callbacks-off core repeat. The six runs used
the same node, GH200, bundle, rollout geometry and source revision. This
modest difference should be read with the earlier path-dependent result: it
does not support the claim that D is dramatically slower. The run-level JSON
records and driver log are under
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt43/`.

Attempt44 profiled one 20,480-step D core run with Python `cProfile` on the
same source, node, seed, bundle and geometry. Profiling adds overhead, so its
285.9-second duration is **not** a throughput estimate. It collected 49.3
million calls. Within the 275.5-second PPO `.learn()` interval, rollout and
framework work used 178.1 seconds; PPO updates used 97.3 seconds. The leading
call stacks were:

| Hot path | cProfile cumulative time | Interpretation |
|---|---:|---|
| `MTFReasoningEncoder.forward` | 171.7 s | Most time is spent extracting nine timeframe streams during rollout and PPO action evaluation |
| `_encode_valid_suffix` | 157.7 s | Called 28,530 times; strongest concrete optimization lead in the current profile |
| `torch.conv1d` | 64.8 s self time | Material TCN cost inside the valid-suffix encoder path |
| vector-env `posix.read` / `SubprocVecEnv.step_wait` | 20.9 / 20.2 s | Worker IPC is measurable but below encoder work in this profile |

The trainer used about 1.17 CPU cores on average from 64 allocated, while the
profiled GPU peak allocation was about 1.10 GiB. This identifies encoder
forward and valid-suffix handling as the next profiling/optimization target;
it does not prove that changing D's encoder improves training wall time. Any
follow-up optimization must be matched across C/D or evaluated separately,
without silently changing the C/D research semantics. The pstats file, top-
function summary and JSON are in
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt44/`.

Attempt52 used PyTorch profiler on one D encoder forward with the real 512-row
observation batch saved for attempt42's microbenchmark. Its masks had mixed
valid lengths in M1 and a few D1 windows; the other seven HTF masks were full.
That single profiled call recorded 17 `aten::item` / device-to-host scalar
reads, 9 `aten::_unique2` reductions and 23 `aten::nonzero` operations. The
profile showed 134.2 ms aggregate CPU operator time and 9.5 ms CUDA operator
time for that instrumented forward. These are profiler-instrumented single-
call measurements, not ordinary inference latency or a training FPS estimate.
They confirm that valid-suffix grouping introduces frequent synchronization
and dynamic grouping work. Raw output is
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt52_profile_suffix_ops.log`;
the bounded profiling script is alongside it. No production encoder code was
changed.

## Estimated 2M wall time

Linear scaling of the attempt-39 training wall times to 2,000,000 steps gives
approximately **6.54 hours for C** and **6.40 hours for D** on separate GH200s.
These estimates include the measured single best-prefix replay, but not setup,
full reporting, or chronological replays.

The full 2025 train replay previously took 50.5 minutes per arm. A 2026 replay
is estimated at 40.1 minutes per arm from its bar count; that duration has not
been measured. If C and D train and replay in parallel on two GH200s, the
estimated critical path is about 8.04 hours before final export. A 25% runtime
reserve raises the estimate to about 10.05 hours, so one 12-hour paired
allocation appears feasible based on measured throughput. This estimate is
not a guarantee; preserve several minutes for setup, result checks, and
checkpoint/report writes.

## Required controls before accepting a 2M run

1. Preserve the matched C/D configs, seed, bundle identity, and eight-env
   geometry. Do not adopt E/F/G encoders inside this pair.
2. Keep the observed 100k account-survival failures visible in the report. A
   larger run may clarify learning behavior; it must not be described as
   passing survival unless its full training replay does so.
3. Keep train-split selection and checkpoint gates separate from the exposed
   2026 report-only evaluation. Do not tune against the latter.
4. Record the deterministic best-checkpoint rejection reason, not just
   `NO_ACTIVE_CHECKPOINT`; the previous 100k prefix diagnostics found daily
   loss events for both arms.
5. Export both arms' required thesis/action traces, per-split diagnostics,
   checkpoint hashes, equity curves, and report figures before the paired
   allocation expires.

## Live allocation observation

At 15:39 EET on 2026-10-28, Slurm job `21247526` was still RUNNING on gpuarm1
with one GH200, 64 CPUs, 512G host RAM, and a 12-hour limit ending at 16:39
EET. The GPU showed 0% utilization and 1 MiB used. A Python process using about
one CPU core and 7.3 GiB RSS belonged to a different user's process tree; it
was left untouched. The interactive allocation shell was preserved. This
allocation was not used to start a fresh 2M C/D campaign.

At 15:43 EET, a current-source, core-only repeat began inside the same existing
interactive allocation (no new Slurm step): three 20,480-step repeats per arm,
seed 42, eight environments, identical rollout geometry, and production
callbacks disabled. It writes to
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt43/`. This is a
throughput diagnostic only; it does not train or replay a 2M policy.

At 16:13 EET, the bounded D cProfile in attempt44 completed. The subsequent
format/lint/type and scoped-test checks ran in the same existing allocation;
no new Slurm job or step was requested. At the latest inventory check, job
`21247526` remained RUNNING on gpuarm1 with one GH200, 64 CPUs, 512G host RAM,
and a 12-hour limit ending at 16:39 EET. No C/D training or evaluation was
active; the persistent allocation shell was preserved.

At 16:44 EET, Slurm still reported `21247526` RUNNING at 12:05 elapsed against
its 12-hour limit. Inside its existing gpuarm1 shell, `nvidia-smi` showed the
allocated GH200 at 0% utilization and 1 MiB used; the user process list
contained only the interactive shell. The node inventory showed both of
gpuarm1's GH200s allocated: one to this idle shell and one to another user's
job. gpuarm2 remained `DOWN+DRAIN+NOT_RESPONDING`. No second GH200 was
available for the matched C/D run, and no job was canceled or changed.

At 16:44:18 EET, Slurm terminated step `21247526.0` for its time limit. `sacct`
now records the parent as `TIMEOUT` after 12:05:04; this was scheduler
termination, not a manual cancellation. At 16:47 EET, gpuarm1 had one GH200
allocated to another user's job and one available, with 8/144 CPUs and 64G of
1.1T host memory allocated; gpuarm2 was still drained and not responding. No
user-owned training or evaluation allocation remained. A two-GH200 request is
not currently eligible, so none was submitted.

## Evidence paths

- C/D phase profiles and process/GPU telemetry:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt39/`
- Repeated core throughput and profiler outputs:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt41/core/`
- Earlier full training replay and complete trade/equity ledgers:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt23/`
- Matched 100k train/test replay report:
  [`variant_cd_100k_full_train_replay_20261028.md`](variant_cd_100k_full_train_replay_20261028.md)
- Decisive policy, thesis, structural, and reporting gates:
  [`variant_d_benchmark_protocol.md`](variant_d_benchmark_protocol.md)
