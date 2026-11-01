# How to read a run

Read a run from identity to outcome. Do not start with its best metric.

1. **Identity:** source commit, resolved config, variant, seed mapping, data
   fingerprints, feature cache hash, schema versions, and hardware.
2. **Training:** requested/effective environment count, PPO rollout geometry
   or SAC replay settings, completed interactions, diagnostics, and checkpoint
   lifecycle.
3. **Evaluation:** chronological partition, policy action mode, execution/cost
   assumptions, account guardrails, and whether the evaluation checkpoint was
   selected without locked OOS.
4. **Outcomes:** equity and drawdown path, fills/position ledger, rejected
   actions, reward components, metrics, uncertainty, and relevant controls.
5. **Evidence level:** classify only the claim supported by retained inputs.
   R2 recomputation is not R3 frozen-checkpoint replay; a smoke/trace is
   software evidence, not a research result.

Use the [result registry](result_registry.md) for current claim boundaries,
[artifact reference](../reference/artifacts.md) for manifest fields, and
[evidence sufficiency audit](evidence_audit.md) for missing inputs. When a
field is absent, say “not recorded” rather than interpreting it as zero.
