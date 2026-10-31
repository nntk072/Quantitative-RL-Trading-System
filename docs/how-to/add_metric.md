# Add an evaluation metric

An evaluation metric summarizes a recorded path; it should not change the
replay or select a policy implicitly.

1. State its formula, units, annualization assumptions, sample requirements,
   and behavior for empty/degenerate trade sets.
2. Derive it from the canonical equity or trade ledger. Do not reconstruct
   fills differently from the simulator.
3. Add tests for known small examples, sign conventions, missing data, and
   boundary cases.
4. Add it to the existing metric/report path so machine-readable and rendered
   outputs agree.
5. Update the [metrics reference](../reference/metrics.md) and ensure the
   result manifest records enough context to reproduce it.

When adding a metric to model selection, update the experiment protocol and
control for repeated comparisons; a descriptive metric is not automatically a
valid selection rule.
