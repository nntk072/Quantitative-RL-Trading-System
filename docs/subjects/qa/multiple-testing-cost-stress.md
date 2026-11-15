# QA for multiple testing and cost stress

**Status:** Five source claims verified against the 2026-11-15 working tree at
HEAD `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `scripts/research/analysis/evidence/analyze_paired_seed_results.py` sorts
   the p-values, weights by remaining family size and applies a capped
   running maximum. The single-primary result leaves its adjusted p-value
   empty.
2. `evaluation/metrics/deflated_sharpe.py::expected_maximum_sharpe` uses
   cross-trial Sharpe dispersion and trial count, with a zero benchmark for
   one or fewer trials or nonpositive dispersion.
3. `evaluation/metrics/deflated_sharpe.py::deflated_sharpe_probability` uses
   non-annualized Sharpe, observation count, skew and non-excess kurtosis.
   Too few observations or nonpositive variance return NaN.
4. `evaluation/reporting/cost_decomposition.py::decompose_fill_costs`
   requires close and cost provenance for summarized positions, allocates
   entry charges over realized sizes and tests the midpoint-to-net residual.
5. `config/research/prospective_research_protocol.yaml::robustness` requires
   finalist cost and missing-quote stress in the prospective study.

## Document and notebook checks

The hub has 150 lines and all 11 required sections. Seven hub links, one
reference link and the hidden notebook target resolve. The reference's
single-primary sign-flip settings and cost status values agree with the
protocol and implementation.

The notebook has matching title and first heading, Python 3 kernel, Tier A,
bundled synthetic data, CPU, subject, owner and under-60-seconds metadata,
and forced MyST execution. Schema and metadata checks accepted it. Its
assert-bearing code cell has count 1, one saved stdout output and no saved
errors. Saved cell timing is 0.007 seconds. It records adjusted p-values
0.06, 0.06 and 0.20 and zero residuals under both fixed-fill charge schedules.

## Evidence limit

The notebook illustrates arithmetic on fixed synthetic fills. The findings
register records finalist cost and missing-quote sensitivity as unmeasured.
QA inspected the saved notebook without executing a replay.
