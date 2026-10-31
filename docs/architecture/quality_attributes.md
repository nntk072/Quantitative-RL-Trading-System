# Quality attributes

The architecture is designed around the following qualities. They are
engineering objectives enforced through tests and review, not guarantees that
every current workflow fully satisfies them.

| Quality | Meaning in this repository | Evidence or control |
|---|---|---|
| Causal correctness | A decision sees only data available at its timestamp. | Time-alignment and feature leakage tests. |
| Reproducibility | A run can be tied to configuration, inputs, code, and checkpoint. | Run manifests, cache hashes, and checkpoint schemas. |
| Recoverability | Interrupted training can resume from compatible state. | Checkpoint and run-state validation. |
| Modularity | Domain packages can change without reverse dependencies on workflows. | Architecture import-boundary tests. |
| Execution transparency | Fills, costs, risk decisions, and rejections can be inspected. | Trade/fill ledgers and transition diagnostics. |
| Portability | Core contracts are independent of a particular accelerator or broker. | Backend-neutral interfaces and adapters. |
| Scientific validity | Comparisons isolate declared factors and respect chronological evidence roles. | Experiment definitions and validation protocol. |

Performance remains workload- and hardware-dependent. A benchmark must report
its topology, warm-up, measurement boundary, and variability. Faster execution
does not imply equivalent learning unless policy/update semantics remain
matched.
