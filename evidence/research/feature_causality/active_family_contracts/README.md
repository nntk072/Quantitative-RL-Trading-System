# Active feature family contract suite

This current-source batch exercises 14 focused modules covering causal feature
primitives, swing classification, order-block and FVG/IFVG structures, PO3
state and lifecycle, SMT alignment, completed MTF windows, candidate event
projection, feature-contract inventory, assembled prefix behavior, and
observation-validity semantics. It collected and passed 137 tests on the
existing GH200 allocation using the ARM64 project environment.

The exact command and output are retained here. `SOURCE_SHA256SUMS` identifies
the test modules used for this batch. Two existing PyTorch transformer
nested-tensor warnings were emitted; the command exited successfully.

This closes only the listed source-contract regressions. It does not prove all
profile-specific event behavior, attach feature-level validity masks to model
inputs, or establish historical candidate-to-action linkage. See the
all-profile packets alongside this one for measured current-profile behavior.

The production-source hash file is the exact source snapshot observed during
this batch. A later observation-boundary sanitization change has a separate
source and regression packet; it does not retroactively alter this run record.
