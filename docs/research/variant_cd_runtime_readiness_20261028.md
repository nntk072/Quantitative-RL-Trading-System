# Variant C/D runtime readiness update

**Updated:** 2026-10-28, Europe/Helsinki  
**Scope:** measured runtime diagnosis and a pre-run estimate for the matched C/D
2M comparison. This is not the 2M result and does not authorize starting it.

## Decision state

The 100k C/D pilots and their full 2025 training-split replays are complete.
Both policies traded, but both failed the configured account-survival gate in
the replay. The policies and configs remain a matched experimental pair; no
architecture or action-schema changes are proposed here. The user accepted the
seed-42 matched 2M C/D benchmark **after two GH200s are actually available**.
This is a resource-contingent approval: do not start C/D on the current single
GH200 allocation. The corrected runtime estimate below replaces the earlier
10.05-hour estimate quoted with the acceptance request.

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

### Reconcile the two 100k replay reports

The standalone training-only report linked below and the attempt-35 train/test
table above are **different pilot lineages**, not duplicate replays of the
same checkpoint. Do not merge their metrics or present one as a correction of
the other.

| Evidence | Standalone training-only report | Attempt-35 train/test report above |
|---|---|---|
| Training run | attempt21 | attempt32, replayed by attempt35 |
| Source | `16001061f1524ee35dfabb755cf4901d53a9cfbf`, clean | `ce9c30472e9402b50d8ca84cf8f29704436e0d0a` plus dirty patch SHA-256 `346718bb40ca211b6f6ff6c3e05e50c4062872a0e667603473c2c6fa88305e72` |
| C checkpoint / config SHA-256 | `10d26b0499c5057c66f999127ff11ef546f45823411855b4747a7d7bc2f91cf0` / `79acdb13af243ae4cf84baca74cca197ed9852c9bce8c8f57de1d6b827d831b8` | `feef2d48f80b381147dac6ebbe92a9f7ec03fa1999719a5c1ff6060bd77afdc6` / `bdbd72e6cefb6c0a5ed1b0cc4170b645bb925f4d9b5e26b89bf8c6fa1251bfee` |
| D checkpoint / config SHA-256 | `bccec331ff62364c90c154deddc85091e3f0ec65fdeb591a479e538e55041ffd` / `da9f6cb123ae77aecf28ea9e618e1e2e9b2bfbad9dad32d4772792b1f1fedc78` | `2b6c36a2574125d70f643c3726a757d6a99d7af097eca97a43f4317838c8f893` / `3e0e785961ac8cd1b1a0831593e45e1c6b1788c89f252a0b57d580525c9d4f3e` |
| Dashboard / RNG schedule | `eval_every=100000`; `isolate_eval_rng` unset (effective false) | dashboard replay deferred (`eval_every=0`), prior cadence retained at 100000, `isolate_eval_rng=true`; best-prefix selection remained online |
| Replay scope | 2025 training split only | 2025 training plus exposed 2026 report-only interval |

The checkpoints therefore differ both by model weights and by training callback
schedule/RNG isolation. The attempt-35 table supplies the later, broader replay
for its own attempt32 checkpoints; the standalone report remains valid for
attempt21 only. Neither is the result of the proposed 2M comparison.

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

Attempt55 adds the missing C-side stack profile using the same 20,480-step
diagnostic, seed 42, bundle, PPO geometry and benchmark-source hash. Current
main and attempt44's source differ only by documentation; the training,
simulation, model, and learning files are unchanged. Both profiles use the same
GH200 model, but were collected in separate runs with 48 CPUs allocated for C
and 64 for D. Their profiler-instrumented elapsed times are therefore useful
for hot-path comparison, not as a clean throughput A/B result.

| Measure | C, attempt55 | D, attempt44 |
|---|---:|---:|
| PPO `.learn()` wall | 258.4 s | 275.5 s |
| Profiled rollout/framework | 170.8 s | 178.1 s |
| Profiled PPO updates | 87.6 s | 97.3 s |
| `MTFReasoningEncoder.forward` cumulative | 168.1 s | 171.7 s |
| `_encode_valid_suffix` cumulative | 153.9 s | 157.7 s |
| `torch.conv1d` self time | 63.4 s | 64.8 s |
| `posix.read` self / `SubprocVecEnv.step_wait` | 19.6 / 19.0 s | 20.9 / 20.2 s |
| Mean trainer process-tree CPU | 1.19 cores | 1.17 cores |
| Allocated CPUs | 48 | 64 |
| Peak allocated GPU memory | 1.09 GiB | 1.10 GiB |

The C core measured 77.33 steps/s after warm-up versus D's 71.87 steps/s in
these individual profiled attempts. This direction is consistent with the
three-repeat unprofiled diagnostic (88.07 versus 81.79 steps/s), but one
profiled run per arm does not establish a significant architecture or policy
effect. The actionable diagnosis is more stable: both arms spend most of the
profiled rollout time in the shared nine-stream encoder's valid-suffix/TCN
work; IPC is measurable but substantially smaller, and CPU allocation,
aggregate host CPU use, and GPU memory do not indicate resource exhaustion.
Do not modify the matched C/D architecture as a runtime shortcut before the
approved benchmark.

Attempt55 artifacts are under
`/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt55_cprofile/`.

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

The previous 10.05-hour estimate omitted the dashboard replay cadence enabled
by the current canonical config. It is superseded below.

The current base config sets `training.dashboard.eval_every=100000`,
`prior_every=100000`, and `isolate_eval_rng=false`; the C/D 2M overlays do not
override those keys. A fresh canonical run therefore performs dashboard
evaluation during training, unlike attempt39's throughput profile (dashboard
disabled) and unlike attempt32 (dashboard deferred, RNG isolated). Do not
silently alter these settings to make the estimate fit.

Using attempt39's measured 100,352-step wall times and adding twenty observed
dashboard replay costs from attempt21 gives a conservative training estimate
of **7.72 hours for C** and **7.54 hours for D**. Attempt21's own measured
`learn()`/best-evaluation timing projects a lower **6.06/6.19-hour** training
estimate at the same cadence. This spread reflects distinct measured
throughput lineages and should be treated as runtime uncertainty, not as two
different config predictions.

The 2025 full-split replay took about 50.5 minutes per arm. A 2026 replay is
estimated at 40.1 minutes per arm from its bar count; this duration has not
been measured. Adding both final replays and a 25% reserve yields a paired
critical-path estimate of **about 9.46–11.54 hours** when C and D run in
parallel. The upper estimate leaves little margin inside a 12-hour allocation;
setup, reporting, checkpoint verification, or slower-than-measured execution
could exceed it. At the documented cap of 12 GH200 GPU-hours per request, a
two-GH200 request covers six hours of wall time, so this estimate requires a
second allocation window queued with an explicit non-overlapping dependency
if the first window is six hours. This is a planning range, not authorization
or a guarantee.

## Required controls before starting the accepted 2M run

1. The user has approved this seed-42 comparison once two GH200s are
   available. Preserve the matched C/D configs (C SHA-256
   `fa27bb63debc77cf3461ff29e385b0d2fc80a7c121a7cc4a908ae9c10298b569`; D
   SHA-256 `d97017d8c354cdb5b24544359c50396f7a53096429f21c6f502d9325a9079f39`),
   bundle identity, and eight-env geometry. Do not adopt E/F/G encoders inside
   this pair.
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
allocation was not used to start a fresh 2M C/D experiment run.

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
user-owned training or evaluation allocation remained. At 18:11 EET, job
`21264865` was RUNNING on gpuarm1 at 1:04 elapsed of 6:00, using one GH200,
48 CPUs and 256 GiB. Another user's job `21261802` held gpuarm1's second GH200
at 3:00 elapsed of 4:00, with 8 CPUs and 64 GiB. The node had 56/144 CPUs
allocated and 327,680/1,100,000 MiB host memory allocated. gpuarm2 remained
`DOWN*` (not schedulable). Neither two free GPUs nor a paired C/D allocation
was currently available; C/D remains unstarted.

At 18:16 EET, the live inventory still showed job `21264865` RUNNING on
gpuarm1 (1 GH200, 48 CPUs, 256 GiB; 1:09 elapsed of 6:00). The second GH200
remained assigned to another user's job `21261802` (8 CPUs, 64 GiB; 3:05 of
4:00). gpuarm1 had 56/144 CPUs allocated and 327,680/1,100,000 MiB host RAM
allocated, leaving 88 CPUs and 772,320 MiB unallocated. Both configured GH200s
were allocated. gpuarm2 remained `DOWN+NOT_RESPONDING`, with no jobs and no
schedulable CPUs or GPUs. No new request was made; the matched C/D experiment run
still lacks two simultaneously available GH200s.

## Evidence paths

- C/D phase profiles and process/GPU telemetry:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt39/`
- Repeated core throughput and profiler outputs:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt41/core/`
- Matched C/D runtime stack profiles:
  D: `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt44/`; C:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt55_cprofile/`
- Earlier full training replay and complete trade/equity ledgers:
  `/scratch/work/nguyenl37/mtf_cd_benchmark_20261027/attempt23/`
- Matched 100k train/test replay report:
  [`variant_cd_100k_full_train_replay_20261028.md`](variant_cd_100k_full_train_replay_20261028.md)
- Decisive policy, thesis, structural, and reporting gates:
  [`variant_d_benchmark_protocol.md`](variant_d_benchmark_protocol.md)
