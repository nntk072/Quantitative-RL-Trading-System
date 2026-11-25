# Coverage policy

Coverage is measured from the checked-out target branch's declared product
packages, not from tests, scripts, or repository tooling. The CI
`coverage-report` job also includes
`research_tools.compute.audits.pretraining_readiness_task_runner` so its
artifact SHA-256 provenance code stays visible in ordinary reports; the
resulting `research_tools` row is informational and has no package baseline.
The job combines unit and integration data, compares each product package with
the main baseline in `tools/quality/coverage_baseline.json`, and fails if line
coverage falls below that baseline. Branch coverage is reported but is not
gated. The product floor target is 100% line coverage over the product
packages, which is not yet met; the regression gate is the enforced rule today.

## Latest measured coverage

CI run `45668584827` at target-branch head `13fde0fb` (same source tree as merge
`6755417e`) measured 36,395 of 44,790 product statements covered (81.26%) and
11,337 of 16,428 branches covered (69.01%). The line gap is 8,395 statements.
Branch coverage is informational only. The enforced check is line regression
against the main baseline above; this artifact measures `perf/env-step-speedup`
and is not a repository-wide coverage percentage.

| Product package | Line coverage |
|---|---:|
| `artifacts` | 95.28% |
| `compute` | 78.08% |
| `configuration` | 97.49% |
| `decisioning` | 95.53% |
| `evaluation` | 82.31% |
| `experiments` | 73.02% |
| `features` | 94.15% |
| `integrations` | 56.66% |
| `learning` | 81.91% |
| `live` | 82.84% |
| `market_data` | 87.68% |
| `models` | 95.47% |
| `simulation` | 84.29% |
| `trading` | 87.22% |
| `training` | 65.71% |

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
