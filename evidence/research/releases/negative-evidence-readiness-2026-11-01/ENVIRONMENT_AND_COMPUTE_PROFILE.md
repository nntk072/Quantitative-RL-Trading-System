# Environment and compute profile

## Observed local verification environment

| Property | Observed value |
|---|---|
| Host architecture | x86_64 |
| Python | 3.12.14 |
| PyTorch | 2.14.0+cu130 |
| Stable-Baselines3 | 2.9.0 |
| CUDA visible to this process | No |
| Focused pytest result | 54 passed, 2 warnings |

The PyTorch build identifies a CUDA-capable package build; `torch.cuda.is_available()`
was false on the inspected host. This is not a GPU benchmark or GH200
utilization measurement.

## Campaign identity

The recovered selected pair records seed 50, 2M training steps, 32
environments, and source commit
`b93642a368439a7838c3107c25fd4999b32bc028`. Exact per-arm config and artifact
hashes are in the external campaign directory and reconciliation report; they
are not copied into the tracked release. One separate 20M scratch campaign is
not the selected run and is excluded from its evidence.

## Resource statement

No training or checkpoint replay was started for this readiness snapshot. Two
bounded CPU input-audit jobs ran sequentially from the named tmux session on
`csl34`, each requesting 8 CPUs, 12 GB, and one hour. Preliminary job
`21339889` completed in 13:01 with 4,660,972 KiB peak RSS; its tick-quality
metric incorrectly counted optional blank `LAST` and `VOLUME` fields as
required and is retained as superseded evidence. Corrected job `21339947`
completed in 13:20 with 1,175,924 KiB peak RSS and 13:17.823 CPU time; it
verified all 39 manifest input hashes and generated the current audit linked
from the data-provenance record. Detailed job `21340127` completed in 13:46
with 2,046,444 KiB peak RSS, 13:39 accumulated CPU time, and 15,511.98 MiB
reported disk reads while deriving per-column missingness and timestamp-tie
quote categories from those inputs. No claim is made about GH200 utilization,
GPU speed, or training throughput. Do not infer these from historical campaign
durations.
