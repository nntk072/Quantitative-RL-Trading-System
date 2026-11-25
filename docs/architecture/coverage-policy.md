# Coverage policy

Coverage is measured from the checked-out target branch's declared product
packages, not from tests, scripts, or repository tooling. The CI
`coverage-report` job also includes
`research_tools.compute.audits.pretraining_readiness_task_runner` so its
artifact SHA-256 provenance code stays visible in ordinary reports. Its
`research_tools` row and the all-source aggregate are informational; product
totals and the regression gate use only the 15 product packages listed below.
The job combines unit and integration data, compares each product package and
the product aggregate with the main baseline in
`tools/quality/coverage_baseline.json`, and fails if line coverage falls below
that baseline. Branch coverage is reported but is not gated. The product floor
target is 100% line coverage, which is not yet met; the regression gate is the
enforced rule today.

## Latest measured coverage

CI run `45687911793` at target-branch head `26ad3e8d` measured 36,413 of
44,790 product statements covered (81.30%), with 8,377 statements missing.
Product branch coverage is 11,337 of 16,428 (69.01%), informational only.
The artifact's all-source total is 36,444/44,873 lines and 11,337/16,442
branches; it includes the informational `research_tools` helper at 31/83 lines
(37.35%) and 0/14 branches. This artifact measures only
`perf/env-step-speedup`; it is not a repository-wide coverage percentage.

| Product package | Covered / statements | Line coverage |
|---|---:|---:|
| `artifacts` | 343/360 | 95.28% |
| `compute` | 919/1,177 | 78.08% |
| `configuration` | 194/199 | 97.49% |
| `decisioning` | 577/604 | 95.53% |
| `evaluation` | 9,566/11,600 | 82.47% |
| `experiments` | 2,373/3,250 | 73.02% |
| `features` | 3,908/4,151 | 94.15% |
| `integrations` | 965/1,703 | 56.66% |
| `learning` | 2,816/3,438 | 81.91% |
| `live` | 140/169 | 82.84% |
| `market_data` | 2,064/2,354 | 87.68% |
| `models` | 822/861 | 95.47% |
| `simulation` | 6,134/7,277 | 84.29% |
| `trading` | 2,300/2,637 | 87.22% |
| `training` | 3,292/5,010 | 65.71% |

## Exclusions

An exclusion is a `# pragma: no cover` marker in source. Each one needs a reason, and
the reason must be listed here. An unlisted exclusion is a review finding.

| File | Scope | Reason |
|---|---|---|
| `learning/rl/feature_graph.py` | line 63, `FeatureGraphCache._capture` | Needs CUDA graph capture (`torch.cuda.CUDAGraph`, side streams). Covered by GPU runs. |
| `learning/rl/feature_graph.py` | line 141, `GraphedForwardCache._capture` | Needs CUDA graph capture. Covered by GPU runs. |
| `learning/rl/update_graph.py` | line 27, `_StepGraph.__init__` | Needs CUDA graph capture of the PPO minibatch step. Covered by GPU runs. |
| `learning/rl/update_graph.py` | line 75, `_StepGraph._step` | Runs only inside the CUDA graph capture above. |

The replay-cache logic around each capture is covered on CPU by
`tests/unit/learning/test_graph_replay_cache.py`, which fakes the capture step.

## Not yet excluded, and not yet covered

The uncovered lines in every product package remain in scope and are not
excluded. Package gaps are tracked as open work in the goal reading plan.
