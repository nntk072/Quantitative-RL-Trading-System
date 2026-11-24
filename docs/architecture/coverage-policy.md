# Coverage policy

Coverage is measured per product package. The CI `coverage-report` job combines
unit and integration data, compares each package with the main baseline in
`tools/quality/coverage_baseline.json`, and fails if line or branch coverage falls
below that baseline. The product floor target is 100% line coverage over the
product packages, which is not yet met; the regression gate is the enforced rule today.

## Exclusions

An exclusion is a `# pragma: no cover` marker in source. Each one needs a reason, and
the reason must be listed here. An unlisted exclusion is a review finding.

| File | Scope | Reason |
|---|---|---|
| `learning/rl/feature_graph.py` | `FeatureGraphCache._capture` | Needs CUDA graph capture (`torch.cuda.CUDAGraph`, side streams). Covered by GPU runs. |
| `learning/rl/feature_graph.py` | `GraphedForwardCache._capture` | Needs CUDA graph capture. Covered by GPU runs. |
| `learning/rl/update_graph.py` | `_StepGraph.__init__` | Needs CUDA graph capture of the PPO minibatch step. Covered by GPU runs. |
| `learning/rl/update_graph.py` | `_StepGraph._step` | Runs only inside the CUDA graph capture above. |

The replay-cache logic around each capture is covered on CPU by
`tests/unit/learning/test_graph_replay_cache.py`, which fakes the capture step.

## Not yet excluded, and not yet covered

Product packages below the 100% target include `compute` (about 56% line), `integrations`
(about 53%), `experiments` (about 61%) and `training` (about 66%). Their gaps are not
excluded: they are tracked as open work in the reading plan.
