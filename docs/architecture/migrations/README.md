# Architecture migrations

This directory contains durable records of completed repository migrations.
It is not a task queue or a home for implementation plans. Each record should
identify the old and new interface, affected paths/artifacts, compatibility
behavior, verification, and any remaining legacy names.

## Migration principles

- Preserve existing run records, data, and checkpoints; a path cleanup is not
  permission to rewrite historical evidence.
- Audit code, configuration, documentation, tests, and output writers before
  changing a public path.
- Give serialized meaning changes an explicit version and translation path.
- For archival moves, retain checksums and a reversible mapping to the new
  location.
- Remove compatibility aliases only when no supported artifact or consumer
  still depends on them.

Current migration evidence:

- `experiment_run_name_migration.json` records an earlier experiment-run path
  migration. Its historical identifiers remain evidence, not recommendations
  for current names.
- `entry_idea_opportunity_count_evidence.json` and
  `research_evidence_moves.json` record machine-evidence path migrations with
  source-to-destination checksums.

See [cross-cutting architecture concerns](../cross_cutting_concerns.md) and
[checkpoint compatibility](../../reference/checkpoint_compatibility.md).
