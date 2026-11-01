# Changing a serialized schema or cache identity

Observation, action, checkpoint, manifest, and feature-cache schemas are
compatibility boundaries. A field rename, width/order change, unit change,
mask semantic change, or feature-time change can alter saved artifact meaning
even when tensor shapes still match.

## Change procedure

1. Identify the owning schema/contract and its consumers with the architecture
   map and scoped tests.
2. Decide whether the change is backward-compatible, migratable, or requires a
   new schema version. Document the semantic change, not only the version.
3. Update the versioned schema description and generated reference source.
4. Implement a deliberate migration or fail-fast compatibility check. Do not
   silently reinterpret old checkpoint coordinates.
5. Add tests for current serialization, old-version rejection/migration,
   round-trip behavior, and ordering invariants.
6. Update cache content identity whenever generated features or relevant
   inputs change; version and content hash both matter.
7. Update package guide, public API reference, how-to page, and decision
   record. Preserve historical evidence and its old schema identity.

Start with [checkpoint compatibility](../reference/checkpoint_compatibility.md),
[cache and schema versions](../reference/cache_and_schema_versions.md),
[artifact manifests](../reference/manifest_schemas.md), and
[testing practices](../development/testing.md).
