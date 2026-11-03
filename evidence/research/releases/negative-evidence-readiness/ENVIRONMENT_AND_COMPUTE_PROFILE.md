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

The configured native-versus-M1 bar audit and release-quality gate ran in job
21345323 on csl8 with 4 CPUs and 16 GiB requested. It completed in 6:04 with
6,395,532 KiB peak RSS. Full-tree Ruff passed on 931 files, Mypy on 917 source
files, the expanded suite reported 225 passed/1 accelerator-only skip/2
warnings, and strict Sphinx succeeded.

The final stable-source inventory and software gate ran sequentially in job
21347604 on csl42 with 4 CPUs and 16 GiB requested. Full-tree Ruff passed on
950 files, Mypy on 936 source files, and the expanded suite reported 613
passed/1 accelerator-only skip/2 warnings. The latest docs-only job 21347682
on csl42 completed a forced strict Sphinx rebuild and release-manifest
verification in 3:25, with 1,628,920 KiB peak RSS. The rendered tree contains 2,611 files and has a
per-file SHA-256 manifest at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/rendered_docs_html_20261102_final.manifest.json`.
Those earlier checks used CPU/file-processing resources; they made no claim
about GH200 utilization.

The first combined attempt, job 21345295, stopped after 25 seconds at the
format gate because one source file was unformatted. The formatting issue was
fixed and the exact sequential gate completed in job 21345323. The failed
attempt log is retained outside the repository; no claim is made that the first
attempt ran tests or built docs.

## Current plan closeout

Final validation reused allocation 21376798 on `gpuarm2` (one GH200, 48 CPUs,
512 GB host RAM, 12-hour limit). Four independent CPU-bound audit processes
checked the 19 resolved feature-builder groups in parallel; all 57 real-market
prefix comparisons passed. No training, checkpoint replay, new allocation, or
extra Slurm step was launched. The final full-tree gate passed Ruff format and
lint across 1,042 files, Mypy across 1,028 source files, and 931 scoped tests
with two existing transformer warnings.

The locked ARM `dev` and `docs` extras supplied `myst-nb` for the final strict
Sphinx build. It completed with warnings treated as errors and produced 2,654
files at
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/run-21376798/rendered-docs-html-final-clean`.
Its per-file manifest is stored beside the output with SHA-256
`31bada0902a9909ca51e26bae1c3e420cf40a08da702e8b73b3e579c38ba11fe`.
The documented allocation resources do not establish GPU utilization or a
training-speed claim.
