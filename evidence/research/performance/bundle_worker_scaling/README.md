# Environment worker scaling with shared bundles

This packet compares full-training-split environment workers backed by copied
frames and by the repository's shared environment bundle. Both profiles used
the same GH200 allocation, current benchmark source, resolved base config,
training-data identity, 351,432-row training split, and 256 vector steps at 2,
8, and 16 workers. The bundle artifact was 3.06 GB. Neither profile performed
learner updates or used CUDA.

| Workers | Frames PSS | Bundle PSS | Frames cgroup | Bundle cgroup | Frames steps/s | Bundle steps/s | Frames startup | Bundle startup |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 20.5 GiB | 5.6 GiB | 33.4 GiB | 19.8 GiB | 818 | 838 | 9.8 s | 3.5 s |
| 8 | 49.4 GiB | 6.2 GiB | 62.4 GiB | 20.4 GiB | 2,546 | 2,510 | 31.2 s | 1.7 s |
| 16 | 87.9 GiB | 7.0 GiB | 101.0 GiB | 21.2 GiB | 4,369 | 4,414 | 60.9 s | 1.9 s |

The shared bundle reduced measured process-tree PSS by 73%, 87%, and 92% at
2, 8, and 16 workers. Environment throughput stayed within 1.5% at 8 workers
and improved by about 1% at 16. This is a strong memory-scaling result for the
bundle-backed path. It supports using that path when selecting memory-bound
worker counts, subject to the actual learner and evaluation pipeline profile.
The existing 16-case bundle equivalence module also passes against the current
source in the same allocation.

Preparation timings are not an apples-to-apples result: bundle was run first
with a cold feature cache and frames second after cache warmup. The bundle
profile recorded 73.8 s for data preparation and 10.5 s to build the bundle;
the later frame pass recorded 14.4 s for data preparation. Use those values as
run observations only, not as a bundle-versus-frames speed comparison.

The profiles measure environment construction, reset, memory, and short vector
stepping only. Learner forward/update, checkpoint I/O, frozen full-period
evaluation, GPU/VRAM utilization, report generation, and archive writeback
remain unmeasured. This does not validate a training campaign worker count or
complete the Stage L end-to-end performance gate.

Reproduce both profiles inside a compatible existing allocation:

```bash
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --full-train --env-counts 2 8 16 --steps 256 --data-source bundle \
  --output evidence/research/performance/bundle_worker_scaling/bundle_profile.json
.venv/bin/python scripts/research/benchmarks/measure_env_memory.py \
  --full-train --env-counts 2 8 16 --steps 256 --data-source frames \
  --output evidence/research/performance/bundle_worker_scaling/frames_reference_profile.json
.venv/bin/python -m pytest \
  tests/unit/simulation/test_environment/test_bundle_env_equivalence.py -q
```

The exact run metadata, report hashes, and source hashes are recorded alongside
this README. The validation output and wall-clock logs are preserved outside
the repository in the agent plan directory.
