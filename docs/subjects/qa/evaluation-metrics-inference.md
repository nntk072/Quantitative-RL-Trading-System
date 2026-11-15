# QA for evaluation metrics and inference

**Status:** Five source claims verified against the 2026-11-15 working tree at
HEAD `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `evaluation/metrics/performance.py::max_drawdown` uses the running
   equity peak and clips the fractional decline to the range zero to one.
2. `evaluation/metrics/performance.py::completed_position_trade_pnls`
   groups usable close PnL by completed position, prefers a valid position
   total, and counts usable fills separately. Its incomplete count includes
   all observed position IDs without a reconstructible completed PnL.
3. `evaluation/metrics/performance.py::compute_metrics` requires a positive
   integer annualization input and passes it to bar-return Sharpe and Sortino.
4. `evaluation/metrics/bootstrap.py::paired_metric_difference_ci` uses
   identical contiguous block indices for both aligned series in each draw.
5. `scripts/research/analysis/evidence/analyze_paired_seed_results.py`
   computes a treatment-minus-control difference per seed and resamples
   the differences with replacement for the mean percentile interval.

## Document and notebook checks

The corrected hub has 161 lines and all 11 required sections. Eight hub
links, both reference links and the hidden notebook target resolve. The
hub and reference now distinguish incomplete PnL reconstruction from open
exposure. The hub cites direct integration coverage for
`compare_matched_returns` and describes the related unit coverage separately.

The notebook has matching title and first heading, Python 3 kernel, Tier A,
bundled synthetic data, CPU, subject, owner and under-60-seconds metadata,
and forced MyST execution. Schema and metadata checks accepted it. Its
assert-bearing code cell has count 1, one saved stdout output and no saved
errors. Saved cell timing is 7.810 seconds. It shows one completed position,
three realized fills, one open fixture position, 25% drawdown, 15% payout-aware
return and a 1.00% paired mean difference.

## Evidence limit

The saved notebook contains synthetic path arithmetic. QA inspected its
saved state. Refreshed empirical metrics and seed inference remain unmeasured
in the findings register.
