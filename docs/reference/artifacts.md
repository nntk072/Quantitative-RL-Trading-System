# Artifact types

Artifacts are identified by logical kind and ID independently of the filesystem path used to store them. Current artifact types include resolved configuration snapshots, feature caches, checkpoints, training records, evaluation ledgers, reports, and derived plots.

## Provenance

A manifest may include a schema version, creation time, retention class, parent artifact IDs, and provenance fields. Run records should connect the source/config/data identity to the checkpoint and evaluation outputs. Parent links express lineage; they do not prove that an evaluation is scientifically valid.

## Storage behavior

Artifact writers use shared layouts and atomic write helpers where supported. Retention categories distinguish run-retained evidence from rebuildable caches and disposable temporary files. Never delete a run output based solely on its extension or size; identify its lineage and recovery value first.

See the [artifact package guide](../modules/artifacts.md), [reproducibility](../concepts/reproducibility.md), and [checkpoint compatibility](checkpoint_compatibility.md).
