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
target remains 100% line coverage; the main-baseline regression rule is the
enforced gate today.

## Latest measured coverage

PR CI run `45720631954` at source commit `54abfbb8` measured 37,247 of
44,898 product statements covered (82.96%), with 7,651 statements missing.
Product branch coverage is 11,580 of 16,472 (70.30%), informational only.
The artifact's all-source total is 37,278/44,981 lines (82.87%) and
11,580/16,486 branches (70.24%); it includes the informational
`research_tools` helper at 31/83 lines (37.35%) and 0/14 branches. This
artifact measures only `perf/env-step-speedup`; it is not a repository-wide
coverage percentage.

| Product package | Covered / statements | Line coverage |
|---|---:|---:|
| `artifacts` | 343/360 | 95.28% |
| `compute` | 919/1,177 | 78.08% |
| `configuration` | 194/199 | 97.49% |
| `decisioning` | 577/604 | 95.53% |
| `evaluation` | 9,758/11,600 | 84.12% |
| `experiments` | 2,470/3,250 | 76.00% |
| `features` | 3,908/4,151 | 94.15% |
| `integrations` | 965/1,703 | 56.66% |
| `learning` | 2,853/3,438 | 82.98% |
| `live` | 140/169 | 82.84% |
| `market_data` | 2,169/2,462 | 88.10% |
| `models` | 822/861 | 95.47% |
| `simulation` | 6,138/7,277 | 84.35% |
| `trading` | 2,309/2,637 | 87.56% |
| `training` | 3,682/5,010 | 73.49% |

## Exclusions

An exclusion is a `# pragma: no cover` marker in source. Each one needs a reason, and
the reason must be listed here. An unlisted exclusion is a review finding.

| File | Scope | Reason |
|---|---|---|
| `live/paper/__init__.py` | line 3, empty package marker | Declares no exports and has no runtime behavior. |
| `experiments/provenance/__init__.py` | line 3, empty package marker | Declares no exports and has no runtime behavior. |
| `simulation/backtest/cross_validation/utils/__init__.py` | line 3, empty package marker | Declares no exports and has no runtime behavior. |
| `integrations/mt5/adapters/data.py` | lines 16, 25, abstract method bodies | Abstract interfaces are exercised through concrete adapters; these base raises have no implementation behavior. |
| `integrations/mt5/adapters/strategy.py` | line 20, abstract method body | Abstract interface is exercised through concrete strategies; the base raise has no implementation behavior. |
| `integrations/mt5/adapters/trader.py` | lines 19, 32, 45, 58, 71, 84, abstract method bodies | Abstract interfaces are exercised through concrete traders; these base raises have no implementation behavior. |
| `features/pipeline/feature_matrix_builder.py` | line 887, matrix normalization persistence postcondition | Every valid path with `fit_state_path` captures the matrix fit before reaching this invariant guard; it only detects an internal control-flow regression. |
| `trading/policy/config.py` | line 146, optional max-loss percentage guard | The frozen config's `__post_init__` always resolves the optional input to a percentage before `validate()` can run. |
| `market_data/quality_audit.py` | lines 389-391, pandas cross-tab key invariant | `DataFrame.value_counts()` over the fixed two-column frame yields a two-element tuple; malformed keys require violating the library contract. |
| `features/technical/indicators.py` | line 354, non-native session clock timezone guard | The called clock resolver returns an aware index for supported non-native clocks and rejects naive FTMO indexes first. |

CPU fakes in `tests/unit/learning/test_graph_replay_cache.py` exercise the
capture orchestration and replay-cache logic without requiring CUDA. The
PPO minibatch math is exercised with a CPU policy and fake capture APIs in
`tests/unit/learning/test_update_graph_fake_capture.py`. Hardware replay parity
remains a separate CUDA validation concern; it does not justify excluding the
CPU-executable math and orchestration from product line coverage.

## Not yet excluded, and not yet covered

The uncovered lines in every product package remain in scope and are not
excluded. Package gaps are tracked as open work in the goal reading plan.
