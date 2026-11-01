# Training reports

`training/reporting/` renders training diagnostics such as learning curves,
losses, entropy, clipping, and learning-rate plots from recorded training
metrics. It reports optimizer and rollout behavior; it is not a substitute for
out-of-sample trading evaluation.

Keep plots reproducible from saved metrics and distinguish unavailable values
from zero. Focused tests are in `tests/unit/training/` and
`tests/unit/evaluation/`.
