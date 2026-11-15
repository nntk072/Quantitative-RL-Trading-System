# Trade setups

**Status:** draft
**Use this when:** You need to understand how entry-idea features become stable eligible candidate IDs before a policy or decision provider selects one.

## Summary and use this when

The feature pipeline builds per-idea, timeframe, and direction eligibility signals. A canonical catalog maps those exact tuples to stable IDs, with ID zero reserved for no-trade. The catalog is a wire contract; it does not assert that any setup has positive expected return.

- Use this guide when reading or changing the setup candidate catalog.
- Use it when checking eligibility-mask width, feature names, or source-event identity.
- Use the action-schema guide for policy coordinates and their persisted meaning.

## Key terms

- [Trade setup](../../glossary.md)
- [Entry idea](../../glossary.md)
- [Action schema](../../glossary.md)
- [OOS](../../glossary.md)

## Explanation

### The rule

`decisioning/trade_setup.py` defines six idea families, nine candidate timeframes, two directions, and `NO_TRADE_ID = 0`. The canonical catalog creates a stable ID for every idea/timeframe/direction combination. The resulting category count is 109: one no-trade choice plus 108 executable candidates.

`features/context/entry_ideas.py::build_entry_idea_features` builds feature columns from the upstream context signals. For an active candidate, `features/context/trade_setup_candidates.py::active_trade_setup_candidates` checks the exact `entry_idea_{idea}_{timeframe}_{long|short}` feature. It does not infer eligibility from another timeframe or from a related setup family.

`trade_setup_candidate_mask` returns a fixed-width eligibility mask and always leaves the no-trade category enabled. `trade_setup_candidate_feature_columns` maps executable IDs to their feature columns. Candidate ID conversion uses the canonical catalog; do not reconstruct category meaning from a vector width or a locally guessed ordering.

Candidate event identity is separate from eligibility. `trade_setup_candidate_event_identities` assigns an identity only when the candidate's source-time fields are present and unambiguous. Missing or conflicting source times are recorded as statuses; the decision row timestamp is not substituted as a source-event timestamp.

### Why it works this way

Eligibility features are produced from market structure context, while the catalog and action schema provide stable semantic names across consumers. Keeping these layers separate allows a model output to be checked against the exact candidate definition and persisted schema.

No-trade remains an explicit, always-eligible option so a mask cannot force selection of an executable candidate when every setup signal is inactive. Event identity carries provenance for a chosen candidate but does not change the catalog ID or the underlying feature signal.

### Failure modes

- Interpreting the same numeric ID with a locally rebuilt order can silently change persisted meaning.
- Building a mask from every numeric column rather than exact candidate features can activate ineligible choices.
- Removing no-trade from the mask makes an empty setup row impossible to represent safely.
- Using observation width alone to identify a schema ignores version and coordinate meaning.
- Filling missing event timestamps from the policy row time fabricates source provenance.
- Describing a candidate as validated or profitable without a registered result exceeds the software contract.

## Worked example

The Tier A notebook selects one catalog entry, encodes its center value, decodes it back to the same ID, and builds an eligibility mask from its exact feature column. It shows wire-contract mechanics only; no market data or strategy performance result is used.

```{toctree}
:hidden:

examples/trade-setups
```

## Tasks

- Review the [trade-setup catalog](../../reference/trade_setup_catalog.md) before changing IDs or idea names.
- Check [action schemas](../../reference/action_schemas.md) before changing serialized policy coordinates.
- Use the [observation schemas](../../reference/observation_schemas.md) for mask and observation contracts.
- Use the [feature catalog](../../reference/feature_catalog.md) to trace candidate-producing columns.

## Contract

| Item | Contract | Source |
|---|---|---|
| Ideas | PO3, order block, standard deviation, FVG retest, IFVG retest, IFVG unretested | `decisioning/trade_setup.py::TRADE_SETUP_IDEAS` |
| Timeframes | M1, M3, M5, M10, M15, M30, H1, H4, D1 | `decisioning/trade_setup.py::TRADE_SETUP_TIMEFRAMES` |
| Directions | Long (`1`) and short (`-1`) | `decisioning/trade_setup.py::TRADE_SETUP_DIRECTIONS` |
| No-trade | Candidate ID zero; mask entry is always enabled | `decisioning/trade_setup.py::NO_TRADE_ID`; `features/context/trade_setup_candidates.py::trade_setup_candidate_mask` |
| Candidate count | One no-trade plus 108 idea/timeframe/direction combinations | `decisioning/trade_setup.py::TRADE_SETUP_CATEGORY_COUNT` |
| Eligibility | Exact per-candidate entry-idea feature column | `features/context/trade_setup_candidates.py::active_trade_setup_candidates` |
| Event identity | Requires complete, unambiguous candidate source times | `features/context/trade_setup_candidates.py::trade_setup_candidate_event_identities` |

## Verify

- `tests/unit/decisioning/test_trade_setup_contract.py` covers catalog and ID semantics.
- `tests/unit/decisioning/test_trade_setup_properties.py` checks catalog properties.
- `tests/unit/features/test_trade_setup_candidate_events.py` checks feature-column eligibility and event identities.
- `tests/unit/decisioning/test_candidate_geometry_contract.py` covers candidate-geometry schema contracts.
- Research evidence: setup performance, selection quality, and OOS generalization are **not measured** by this reference or its notebook.

## Limits and common mistakes

- The ID catalog is a compatibility contract, not a ranking of setup quality.
- Feature eligibility does not mean the market state was executable at a broker.
- A valid event ID requires source-time metadata; missing status must remain explicit.
- Candidate geometry exposes fixed feature names and entry hypotheses; it does not guarantee a safe stop, target, fill, or positive reward.
- Locked OOS periods remain excluded from selection; see the [validation protocol](../../research/validation_protocol.md).

## Change checklist

When changing candidate semantics, trace feature construction, exact column names, catalog order, masks, action/observation schema versions, and checkpoint metadata. Update these contracts together only after checking all consumers.

- Add or change candidate IDs through the canonical catalog API.
- Test no-trade on an empty feature row and test one candidate signal at a time.
- Check that candidate feature names match the serialized observation and any saved eligibility manifest.
- Keep source-event identity rules separate from the row where a candidate is selected.
- Search consumer tests for action decoding before changing wire meaning.
- Document research evidence separately from candidate mechanics; if there is no registered evidence, retain the explicit “not measured” statement.

## Review procedure

Use the catalog API as the sole source of candidate IDs and then trace a
candidate from feature eligibility to the consumer that decodes the action.

1. Inspect the declared idea, timeframe, and direction tuples. Catalog ordering
   is serialized meaning: inserting or reordering a tuple can change IDs.
2. Recompute the category count from the declared dimensions and the reserved
   no-trade slot. Check that ID zero remains available even when no feature is
   eligible.
3. Round-trip representative IDs through the canonical center/geometry helpers.
   Include the first and last catalog entries and both direction values.
4. Verify eligibility uses the exact feature column generated for the idea,
   timeframe, and direction. Similar names or partial string matches must not
   activate another candidate.
5. Exercise empty, one-candidate, and multiple-candidate feature rows. The mask
   should preserve no-trade and expose only candidates supported by the row.
6. Inspect event identity separately from row eligibility. A row can select a
   candidate while its source event metadata is incomplete or ambiguous.
7. Follow the encoded action through action decoding and observation schema
   consumers. A catalog contract change may require a schema or checkpoint
   compatibility update even when feature names remain stable.
8. Recheck candidate-geometry values and bounds at the decisioning boundary;
   geometry describes an entry hypothesis and does not certify executable risk.
9. Keep the locked evaluation interval out of catalog, feature, and threshold
   selection. Apply the validation protocol before making any performance claim.

The bundled fixture verifies catalog wiring on synthetic inputs only. It does
not test broker execution, realized fills, candidate selection quality, or
generalization. These research outcomes are **not measured** here.

For a reproducible catalog issue, include the resolved catalog constants, action
schema version, observation feature names, and one minimal feature row. Preserve
no-trade behavior in downstream policy and evaluation adapters, including cases
where every candidate feature is absent or invalid.
Record the exact source revision alongside the schema version so reviewers can
distinguish a stale artifact from a current contract regression.
Include the precise row index and source-event timestamps when reporting a
candidate mismatch. State whether the mismatch is catalog encoding, feature
eligibility, event identity, action decoding, or execution feasibility; these
are separate failure locations with different owners.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
