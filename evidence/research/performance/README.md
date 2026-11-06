# GH200 environment resource profile

`gh200_environment_resource_profile.json` records a bounded, current-source
`TradingEnv` worker-memory and throughput profile on the existing GH200
allocation. It used the final seven calendar days of the configured 2025
training split, 5,460 bars/features, TickBook quotes, and 2, 8, and 16
`SubprocVecEnv` workers. The workload ran 256 vector steps after ten warmup
steps per worker count; it did not train a policy or use CUDA.

The measured process-tree PSS was 2.37 GiB at 2 workers, 4.97 GiB at 8, and
8.44 GiB at 16. The fitted worker slope was 444.5 MiB per worker. Throughput
was 1,031, 2,947, and 5,081 environment steps per second, respectively.
Startup took 5.2, 17.9, and 33.7 seconds. These are bounded slice measurements,
not full training or 64-worker estimates. The cgroup totals include the rest
of the allocation; process-tree PSS is the attributable worker-tree metric.

`gh200_environment_full_train_profile.json` extends the measurement across the
full configured 2025 train split (351,432 rows per symbol/timeframe split) at
2 and 8 workers. Environment-only throughput was 819 and 2,587 steps/s,
startup was 9.3 and 32.1 seconds, and process-tree PSS was 20.6 and 49.5 GiB.
The measured environment payload pickle was 2.52 GB. This run took 62.81
seconds and used no learner updates or CUDA. It does not establish end-to-end
training throughput or justify extrapolation to larger worker counts.

A separate 16-worker full-train run completed in 80.30 seconds. It measured
4,498 environment steps/s, 62.9-second startup, 88.0 GiB process-tree PSS,
and 89.0 GiB cgroup memory. The 2.52 GB serialized environment payload and
about 44.0 GiB base fit-tree PSS show that the full-split working set is large
before adding worker processes. This remains an environment-only
measurement and does not establish learner throughput.

The exact job, node, allocation, config, input reference, script/report hashes,
and limitations are recorded in
[`environment_resource_profile_manifest.json`](environment_resource_profile_manifest.json).
Reproduce the profile inside a compatible existing allocation with:

```bash
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --days 7 --env-counts 2 8 16 --steps 256 --data-source frames \
  --output evidence/research/performance/gh200_environment_resource_profile.json
```

The full-train profile was produced with:

```bash
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --full-train --env-counts 2 8 --steps 256 --data-source frames \
  --output evidence/research/performance/gh200_environment_full_train_profile.json
```

The additional 16-worker measurement used:

```bash
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --full-train --env-counts 16 --steps 256 --data-source frames \
  --output evidence/research/performance/gh200_environment_full_train_profile_16env.json
```

`gh200_environment_full_train_pipeline_profile.json` adds preparation and
worker startup timing plus a run fingerprint. On the full configured train
split, config loading took 0.06 s, the market-data pipeline 2.56 s,
feature-build-or-cache 1.26 s, splitting 0.49 s, and TickBook build/coverage
8.11 s (12.48 s total preparation). Worker create/reset took 9.08/31.68/62.16
seconds at 2/8/16 workers. The 256-step vector phase took 0.61/0.79/0.91 s,
with 834/2,582/4,489 environment steps/s. The process was restricted to CPUs
0–47. This profile measured no learner update, checkpoint, frozen evaluation,
report rendering, or CUDA work, so it is a component profile rather than the
end-to-end performance acceptance run.

A separate 32-worker full-split extension used the same current data/config
fingerprint and 48-CPU affinity. It completed in 144.45 seconds, including
12.59 seconds of data preparation and 124.57 seconds to create/reset workers;
the 256-step vector phase took 1.14 seconds and reached 7,167 environment
steps/s. Process-tree PSS was 165.0 GiB and cgroup memory was 166.3 GiB. This
shows measured scaling through 32 workers on the current node, while keeping
the learner, GPU, checkpoint, evaluation, and report stages unmeasured.

Reproduce it inside a compatible existing allocation with:

```bash
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --full-train --env-counts 32 --steps 256 --data-source frames \
  --output evidence/research/performance/gh200_environment_full_train_profile_32env.json
```

Reproduce it inside a compatible existing allocation with:

```bash
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --full-train --env-counts 2 8 16 --steps 256 --data-source frames \
  --output evidence/research/performance/gh200_environment_full_train_pipeline_profile.json
```

## Shared bundle worker scaling

[`bundle_worker_scaling/`](bundle_worker_scaling/README.md) is a matched
current-source comparison of the full configured train split using frame
copies and the shared environment bundle. In the same GH200 allocation at 2,
8, and 16 workers, process-tree PSS was 20.5/49.4/87.9 GiB for frames and
5.6/6.2/7.0 GiB for the bundle. Throughput was 818/2,546/4,369 versus
838/2,510/4,414 steps/s. The 16-case environment equivalence module passed.
This identifies a strong memory-scaling option, but the profile remains
environment-only and does not validate training throughput or a campaign
worker count. Feature-cache preparation times are not compared because the
bundle run warmed the cache before the frame-backed run.
