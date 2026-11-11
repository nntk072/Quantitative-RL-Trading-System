# Cache and schema versions

Cache and schema versions identify changes that can make a stored artifact
incompatible with the code that reads it. They supplement content hashes and
serialized schema checks; they do not replace them.

## Feature cache

`features.pipeline.feature_cache_identity.FEATURE_CACHE_VERSION` currently
uses `v44-wilder-adx`, invalidating cached ADX values after switching to
Wilder smoothing. The feature cache identity also hashes the
resolved feature configuration, market input indexes and values, optional
training mask, and other settings that affect feature output.

Increment the feature cache version when a change alters the feature matrix's
columns, ordering, dtypes, values, causal timing, or normalization semantics in
a way that should invalidate existing caches. Update this version at its
definition in `features/pipeline/feature_cache_identity.py`. Preserve the
identity inputs in `feature_cache_content_hash`; the version string alone is
not a content hash.

## Serialized action and observation schemas

Action and observation compatibility identifiers are owned by their schema
builders and are recorded with checkpoints and run manifests. Change an
identifier when coordinate order, shape, dtype, interpretation, or decoding
behavior changes. Keep migration and deterministic parity checks beside the
schema change.

See [action schemas](action_schemas.md), [observation schemas](observation_schemas.md),
and [checkpoint compatibility](checkpoint_compatibility.md) for the current
contracts and loading rules.
