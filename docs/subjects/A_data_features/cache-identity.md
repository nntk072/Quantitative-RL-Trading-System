# Cache identity

**Status:** Wave A draft
**Use this when:** You need to reuse a feature cache safely, diagnose why a
cache was invalidated, or change a value that affects generated features.

## Summary and use this when

A feature-cache path identifies the symbol, feature-cache version, and a
content-derived digest. The digest includes inputs that can change feature
values or fitted state. The version string is part of the identity but cannot
replace hashing the relevant contents.

- Use this before changing feature inputs, normalization, or timeframe logic.
- Use it when a cache is unexpectedly reused or rebuilt.
- Use the [feature guide](feature-causality-and-normalization.md) for causal
  availability and train-only fitting.

## Key terms

- [Feature-cache identity](../../glossary.md)
- [Artifact](../../glossary.md)
- [Lineage](../../glossary.md)

## Explanation

### The rule

`features/pipeline/feature_cache_identity.py::feature_cache_content_hash`
starts from `FEATURE_CACHE_VERSION`, hashes resolved feature configuration
and relevant timezone/session/cost settings, and includes indexed primary and
secondary data, selected OHLCV/activity columns, timeframe bars, and the full
training mask when provided.

`feature_cache_path` appends the digest to
`{symbol}_features_{FEATURE_CACHE_VERSION}_{digest}.parquet`. The content hash
is intentionally short for path use; it is not an artifact checksum.

### Why it works this way

Configuration-only cache keys miss changes to source rows, timestamps,
secondary instruments, or training masks. A feature version alone also cannot
distinguish two different input files under the same settings. Both explicit
semantic versioning and content identity are required.

The hash includes the complete train mask because identical market rows with
different fit partitions can produce different normalized features. Timeframe
frames are hashed independently so a changed higher-timeframe context cannot
silently reuse a cache built from older bars.

### Failure modes

- Manually changing only `FEATURE_CACHE_VERSION` leaves source identity
  implicit and is not a complete invalidation strategy.
- Omitting a content-affecting input permits stale feature reuse.
- Hashing only the first or last row misses interior corrections.
- Treating the short cache digest as a durable artifact checksum confuses
  lookup identity with integrity verification.

## Worked example

This guide's Tier A notebook builds two tiny deterministic bar frames. It shows
that identical content has a stable identity and that changing one close value
changes the identity. It does not read or write a project cache.

```{toctree}
:hidden:

examples/cache-identity
```

See the [contract reference](../../reference/subjects/cache-identity.md) for a compact input and output summary.

## Tasks

- [Build a feature cache](../../how-to/build_feature_cache.md) after checking
  configuration and source identity.
- For versioning and compatibility checks, see
  [cache and schema versions](../../reference/cache_and_schema_versions.md).

## Contract

| Item | Contract | Source |
|---|---|---|
| Version | `FEATURE_CACHE_VERSION` changes when feature semantics change | `features/pipeline/feature_cache_identity.py` |
| Configuration | Resolved feature settings and relevant timezone/session/cost values | `feature_cache_content_hash` |
| Primary data | Full time index and supported OHLCV/activity columns | `feature_cache_content_hash` |
| Secondary data | Full index and supported content, or explicit `secondary:none` | `feature_cache_content_hash` |
| Timeframe data | Each named timeframe frame contributes its indexed contents | `feature_cache_content_hash` |
| Fit partition | Training mask count and Boolean bytes | `feature_cache_content_hash` |
| Output name | Symbol + version + 16-hex digest + `.parquet` | `feature_cache_path` |

## Verify

- `tests/unit/features/test_cache_hash_full_column.py` checks repeatability and
  changes to full-column data and masks.
- `tests/unit/features/test_feature_cache_and_fit_scope.py` checks path
  identity and configuration sensitivity.
- `tests/unit/tooling/test_documentation_inventory.py` is unrelated to runtime
  cache semantics; use the feature tests above for this contract.
- Research evidence: cache identity verifies invalidation behavior, not data
  provenance by itself.

Independent QA: [five source-claim checks](../qa/cache-identity.md).

## Limits and common mistakes

- A matching cache identity does not prove the source file was obtained from an
  authoritative feed.
- The hash covers the input values enumerated by the implementation; new
  output-affecting inputs must be added when their feature code is introduced.
- Do not edit cache files in place to force a schema change.
- Preserve cache and manifest provenance when investigating a stale result.

## Change checklist

When feature behavior changes, locate every input that can affect the computed
columns and verify that it participates in the identity. Read and update the
canonical cache implementation rather than introducing a second key scheme.

- Keep the semantic feature version aligned with intentional output-contract
  changes, and retain the content digest for input-specific invalidation.
- Include timestamps and complete relevant input columns so interior data
  corrections change the digest.
- Include secondary symbols, per-timeframe frames, and the training mask when
  those values affect computed features or fitted state.
- Add a focused test proving both repeatability and a changed identity after
  mutating one meaningful input.
- Confirm that callers pass the same resolved configuration and frames used to
  build the cache contents.
- Preserve the distinction between a short lookup key and a cryptographic
  checksum for durable artifact integrity.
- Rebuild caches after changing identity semantics; do not edit serialized
  feature files in place to bypass invalidation.

A correct identity prevents a class of stale reuse. It does not prove source
provenance or that a cached feature is economically useful.

## Review procedure

Build identity twice from the same resolved inputs, then change one timestamp,
one interior feature input, one secondary or timeframe value, and one training
mask bit in separate checks. Each meaningful change should invalidate identity.
Also verify a deliberately irrelevant column does not accidentally become a
hidden dependency unless the implementation is extended to hash it. Trace the
computed key into the path constructor and cache caller. These checks establish
the intended invalidation boundary; retain source checksums and manifests for
artifact integrity and provenance.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
