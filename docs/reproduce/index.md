# Reproduce recorded results

A tutorial teaches framework behavior. A reproduction page recomputes a recorded result from frozen inputs. A replay runs a frozen checkpoint, while retraining optimizes a new policy; these are different claims.

## Reproducibility levels

| Level | Meaning |
| --- | --- |
| R1 | Stored report, metrics, or figures can be inspected. |
| R2 | Tracked machine-readable evidence is sufficient to recompute reported tables or figures. |
| R3 | Frozen model, data, and configuration support replay. |
| R4 | Data, source, configuration, seeds, and environment support training rerun. |

A YAML file alone does not establish R4. The [result registry](result_registry) records evidence and known gaps.

## Reproduction notebooks

```{toctree}
:maxdepth: 1

evidence_audit
result_registry
exit_action_semantics.ipynb
p6_monthly_exit_decomposition.ipynb
entry_idea_opportunity_counts.ipynb
environment_trace.ipynb
setup_conditioned_evidence
how_to_read_a_run
```

## Method and evidence

See [reproducibility concepts](../concepts/reproducibility), [evaluation methodology](../research/evaluation_methodology), and the [frozen evidence archive](https://github.com/nntk072/Quantitative-RL-Trading-System/tree/main/evidence/research).
