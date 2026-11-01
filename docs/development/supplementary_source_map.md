# Supplementary source archive map

The supplied LaTeX archive is a supplementary source, not the authority for
software behavior or research results. This map records which material
informed the docs portal and what remains deliberately excluded.

| Source area | Portal destination | Adoption | Verification rule |
|---|---|---|---|
| Problem framing and partial observability | [Foundations](../learn/foundations.md), [partial observability](../concepts/partial_observability.md) | Paraphrased concepts and newly authored equations/diagrams | Confirm observation branches in current `decisioning/` and environment code. |
| Data and walk-forward methods | [Market time and validation](../concepts/data_time_and_validation.md), [validation protocol](../research/validation_protocol.md) | Reconciled with current splitter and cache identity | Current source wins; legacy overlapping fold procedure is explicitly deprecated. |
| PPO and rollout geometry | [PPO rollout geometry](../concepts/ppo_rollout_geometry.md) | Rewritten against current builder and manifest | Do not import archive hyperparameters as current defaults. |
| Action parameterization and position lifecycle | [Trade lifecycle](../concepts/trade_lifecycle.md), [action reference](../reference/action_schemas.md) | New current-code flow diagram and explanation | Verify each stage against the environment and trading contracts. |
| SL/TP and account constraints | [Risk/account limits](../concepts/risk_and_account_limits.md), [risk reference](../reference/risk_and_execution.md) | Concept material retained, exact values delegated to config/reference | Do not treat illustrative values as active limits. |
| Sequence-model background | [Sequence models](../concepts/sequence_models.md), [model reference](../reference/model_architectures.md) | Rewritten and narrowed to registered/current architectures | Verify architecture names and compatibility in encoder registry and builder. |
| Evaluation/statistical inference | [Evaluation statistics](../concepts/research_statistics.md), current research methods | Reused as methodology, not as performance claim | Verify formulas and status in current evaluation code and evidence registry. |
| Result tables and abstract/conclusion | No direct migration | Excluded | The ZIP has TODO result fields and incomplete conclusions; do not invent values. |
| Third-party publication figures | No direct migration | Excluded from the site unless separate reuse permission is documented | The archive license does not automatically license included third-party figures. |
| Project-specific diagrams | New Mermaid diagrams and the portal's own plots | Redrawn in docs source rather than copied as binaries | New source has accessibility text and is reviewed against current code. |

## Source inspection notes

The archive contains manuscript source, chapter text, figure directories, source
scripts, and a bibliography. Its `figure_sources/README.md` identifies several
publication-derived figures and explicitly says to check reuse rights before
publication. The archive README also warns that result tables contain TODOs and
that conclusions are in progress. These statements are treated as
archive metadata, not instructions to copy assets or publish unsupported claims.

The import boundary is therefore conservative: concept explanations may be
re-authored after source verification; numerical results require tracked
repository evidence; a figure must have its own source/provenance record.
