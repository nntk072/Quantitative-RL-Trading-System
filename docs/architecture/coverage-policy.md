# Coverage policy

Coverage is measured per product package. The CI `coverage-report` job combines
unit and integration data, compares each package with the main baseline in
`tools/quality/coverage_baseline.json`, and fails if line coverage falls below
that baseline. Branch coverage is reported but is not gated. The product floor target is 100% line coverage over the
product packages, which is not yet met; the regression gate is the enforced rule today.

## Latest measured coverage

CI run `45600836805` at source `207a4018` measured 35,707 of 44,778 product
lines covered (79.74%) and 11,106 of 16,426 branches covered (67.61%). Branch
coverage is informational only. The enforced check is line regression against
the baseline above. The current line gap is 9,071 statements, so the 100%
target remains open.

| Product package | Line coverage |
|---|---:|
| `artifacts` | 95.00% |
| `compute` | 64.21% |
| `configuration` | 97.49% |
| `decisioning` | 95.53% |
| `evaluation` | 82.31% |
| `experiments` | 60.80% |
| `features` | 94.15% |
| `integrations` | 56.66% |
| `learning` | 81.83% |
| `live` | 82.84% |
| `market_data` | 82.84% |
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
