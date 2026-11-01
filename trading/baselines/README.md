# Baseline strategies

`trading/baselines/` contains reference strategies used for comparison,
including buy-and-hold, rule-based, classical indicator, and learned sweep
classifiers. These provide control policies and diagnostics; they do not
replace the experiment's resolved model or action schema.

Keep baseline inputs and timing assumptions explicit so comparisons do not
benefit from future data or different execution treatment. Focused tests are
in `tests/unit/trading/` and `tests/unit/experiments/`.
