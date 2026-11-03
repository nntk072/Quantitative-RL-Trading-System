# PO3 producer-state validation

The current PO3 producer and lifecycle projection were checked with 29 focused
synthetic cases in the existing GH200 allocation. The cases cover configured
IFVG timeframe alignment, sweep/reclaim/confirmation transitions, exact
bar-indexed event timestamps, conflict separation, replacement/rearm, finalized
sequence prefix invariance, and rejection of ambiguous producer state.

The separate local-data ledger remains diagnostic: its 16,692 accepted setup
sequences and 22 same-bar conflicts are producer outputs, not ground-truth
market events, candidate proposals, policy actions, fills, or trades. Higher-
timeframe pivot/confirmation timestamps retain the float nanosecond precision
limit documented in the parent packet. These tests do not close other event
families or cross-family logical-event cardinality.

Reproduce inside an existing ARM64/GH200 allocation:

```bash
.venv/bin/python -m pytest -q \
  tests/unit/features/test_po3_setup_lifecycle.py \
  tests/unit/features/test_po3_state.py
```

Exact output, current source hashes, and run context are recorded here.
