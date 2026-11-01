# Evaluation statistics and selection risk

No single metric establishes that a policy is useful. Evaluation should state
the target quantity, sample, costs, time split, uncertainty method, and number
of tried variants. Report equity and drawdown paths alongside summary metrics;
trade-level dispersion and decision behavior can reveal failures hidden by an
aggregate return.

## Common metrics

- **Sharpe ratio** summarizes mean excess return relative to return volatility
  under assumptions about sampling and dependence. Annualization and return
  frequency must be stated.
- **Maximum drawdown** is the worst peak-to-trough loss over the measured path;
  its value depends on the sampling and account-equity definition.
- **Profit factor** is gross profit divided by absolute gross loss; it can look
  unstable with few trades and does not show the path risk.
- **Calibration** asks whether predicted probabilities correspond to observed
  frequencies; report bins/sample sizes and uncertainty.
- **Decision diversity** describes action frequencies and conditional
  variation. A policy can achieve a metric by collapsing to one action.

Use the [metrics reference](../reference/metrics.md) for implemented formulas
and contracts. Do not present a metric as implemented unless the run artifact
actually contains it.

## Multiple testing and Sharpe selection

Trying many models, features, seeds, reward variants, or thresholds creates
selection risk: the best observed result may be a favorable noise realization.
The Deflated Sharpe Ratio adjusts a Sharpe-based claim for non-normality and
selection among trials, given its assumptions and an estimate of the effective
search. It does not repair leakage, weak data, or an incomplete search ledger.
Record all eligible trials and selection rules; see the
[experiment design guide](experiment_design.md) and
[validation protocol](../research/validation_protocol.md).

## Statistical inference

Financial outcomes are serially dependent and regime-sensitive. IID standard
errors can be misleading. Prefer paired comparisons on the same dates/seeds
when the design supports them, preserve chronological grouping, and show
confidence intervals plus the resampling unit. A p-value alone does not
quantify economic materiality or reproducibility.

The repository has bootstrap and calibration utilities, paired-seed
statistics, and Deflated Sharpe support. Verify each implementation and input
contract before choosing a method. A deterministic trace is software evidence;
it is not a sample for market-performance inference.

## Cost sensitivity

Recompute the same policy under declared spread/slippage/latency assumptions
and report the full stress grid. Changing costs changes the experiment. Do not
choose a cost scenario after observing which one makes a result favorable.

See [evaluation methodology](../research/evaluation_methodology.md),
[execution costs](execution_and_costs.md), and
[result registry](../reproduce/result_registry.md).
