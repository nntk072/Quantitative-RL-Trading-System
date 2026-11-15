# Market data and sessions contract

**Status:** Wave A draft
**Source of truth:** `market_data/transforms/sessions.py; market_data/transforms/resample.py`

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
| Datetime index | Chronological broker-time timestamps | `load_bars` |
| Session | asia/london/ny/closed label | `add_session_labels` |
| Eligibility | Mask, not row deletion | `ny_session_mask` |

## Configuration and schemas

- Canonical settings: [configuration reference](../configuration.md) and `config/base/default.yaml`.
- Subject explanation: [subject guide](../../subjects/A_data_features/market-data-and-sessions.md).
- Tests and edge cases are listed in that guide's Verify section.

## Errors and limits

- The reference does not establish feed completeness or trading performance.
- Changes to the behavior above require updating the implementation tests and this contract together.
