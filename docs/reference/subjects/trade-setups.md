# Trade setups contract

**Status:** draft
**Source of truth:** `decisioning/trade_setup.py`; `features/context/entry_ideas.py`; `features/context/trade_setup_candidates.py`

## Purpose

This reference describes the stable candidate catalog, exact eligibility features, and explicit no-trade choice. It does not rank or validate setups.

## Inputs

| Name | Type | Meaning | Validation |
|---|---|---|---|
| Candidate ID | Integer | Stable catalog key | Must be in `[0, TRADE_SETUP_CATEGORY_COUNT)`; booleans are rejected |
| Idea | String | One of six canonical setup families | Exact catalog value |
| Timeframe | String | One of nine canonical timeframes | Normalized to uppercase in ID lookup |
| Direction | Integer | `1` long or `-1` short | Exact catalog tuple |
| Feature row | Mapping or Series | Exact per-idea/timeframe/direction signals | Candidate is active only when its own signal is active |

## Outputs

| Output | Type | Meaning |
|---|---|---|
| Candidate catalog | Tuple of `TradeSetupCandidate` | No-trade plus 108 executable tuples |
| Eligibility mask | Float32 array | Fixed width; no-trade slot always one |
| Event identity | Structured record/status | Source-time identity only when fields are complete and unambiguous |

## Configuration and schemas

- Candidate schema version: `TRADE_SETUP_SCHEMA_VERSION`.
- Candidate-geometry observation version and feature names are owned by `candidate_geometry_observation_schema`.
- See [trade-setup catalog](../trade_setup_catalog.md), [action schemas](../action_schemas.md), and [observation schemas](../observation_schemas.md).

## Errors and limits

- Unknown candidate IDs, unsupported semantics, invalid normalized action values, and out-of-range slots raise typed errors in their builders/decoders.
- Vector width is not a substitute for a persisted schema version and coordinate map.
- Performance is not measured by this schema contract.
