# Cache identity contract

**Status:** Wave A draft
**Source of truth:** `features/pipeline/feature_cache_identity.py`

## Purpose

This reference records the small set of input and behavior contracts needed to implement or review this subject. The linked implementation remains authoritative.

## Inputs

| Name | Type | Unit or meaning | Validation |
|---|---|---|---|
| Timestamp index | pandas index | Source row time in configured timezone | Must preserve chronology and availability semantics |
| Feature or market values | pandas Series/DataFrame | Values described in the subject guide | Validate schema at the source boundary |

## Outputs

| Contract | Meaning | Implementation |
|---|---|---|
| Version | Feature semantics version | `FEATURE_CACHE_VERSION` |
| Digest | 16 hex characters from relevant config and indexed input content | `feature_cache_content_hash` |
| Path | Symbol, version, digest, parquet suffix | `feature_cache_path` |

## Configuration and schemas

- Canonical settings: [configuration reference](../configuration.md) and `config/base/default.yaml`.
- Subject explanation: [subject guide](../../subjects/A_data_features/cache-identity.md).
- Tests and edge cases are listed in that guide's Verify section.

## Errors and limits

- The reference does not establish feed completeness or trading performance.
- Changes to the behavior above require updating the implementation tests and this contract together.
