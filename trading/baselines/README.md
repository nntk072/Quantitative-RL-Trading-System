# Baseline strategies

`trading/baselines/` contains reference strategies used for comparison,
including buy-and-hold, rule-based, classical indicator, and learned sweep
classifiers. These provide control policies and diagnostics; they do not
replace the experiment's resolved model or action schema.

Keep baseline inputs and timing assumptions explicit so comparisons do not
benefit from future data or different execution treatment. Focused tests are
in `tests/unit/trading/` and `tests/unit/experiments/`.

The sweep-direction LSTM retains the neutral/no-crossing class and uses the
first future close crossing relative to levels known at the last observed row.
Its current CLI reports the already-exposed evaluation interval only after the
fixed training schedule and labels that output `exposed_report_only`; it is not
a candidate-value model or a confirmatory baseline result.
