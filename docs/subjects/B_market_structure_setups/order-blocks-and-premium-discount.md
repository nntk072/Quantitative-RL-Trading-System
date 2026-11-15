# Order blocks and premium/discount

**Status:** draft
**Use this when:** You need to trace the repository's operational order-block and session-routed premium/discount context definitions.

## Summary and use this when

The order-block module records a price zone from the last opposing candle before a qualifying displacement through a previously confirmed swing. Premium/discount context compares a close with a range midpoint selected by session. Both are configured features; their labels do not establish predictive value.

- Use this guide when adding or interpreting the order-block feature family.
- Use it when checking zone creation, invalidation, retest timing, or raw-level handling.
- Use the [market structure guide](swings-liquidity-smt-po3-fvg-ifvg.md) for swing confirmation and causal levels.

## Key terms

- [Order block](../../glossary.md)
- [Availability time](../../glossary.md)
- [M1 / M3 / M5](../../glossary.md)

## Explanation

### The rule

`features/context/order_blocks.py::build_order_block_features` computes ATR and prior confirmed swing levels, shifting those levels by one row before testing a close-through. A bullish zone requires a bullish displacement through the prior swing high with body size at least `impulse_atr * ATR`; it records the most recent bearish candle within `search_bars`. The bearish rule mirrors this against the prior swing low and a bullish source candle.

The zone spans the source candle's low and high, but it becomes observable on the displacement row. The scalar features provide active state, bounds, midpoint, origin time, age, ATR distance, and retest event. A zone expires after `max_age_bars` or is invalidated by a close through its distal edge. Retest confirmation is recorded later than the bar that first intersects the zone.

`build_order_block_features_with_event_ledger` keeps the scalar latest-zone projection and returns a second per-zone event ledger. The ledger is for diagnostics and does not change the scalar model-facing output.

`features/context/premium_discount.py::build_pd_context_features` derives active range context from broker-time session labels. In London, completed Asia plus the running London range form the composite. In New York, completed Asia and London ranges form it. In Asia, the prior completed calendar-day range is used. It compares close with the active midpoint and emits separate availability and direction fields.

Previous-day and previous-week extrema use completed calendar periods in the index timezone. Raw absolute levels are available for environment diagnostics; raw columns are listed separately from ATR-distance and flag columns so the observation builder can exclude raw prices from normalized model sequences.

### Why it works this way

Swing levels are only usable after confirmation, so the order-block detector uses the previous row's level. The zone origin and the time it becomes available are distinct: the opposing candle defines its bounds, while the later displacement bar makes the pattern observable.

The premium/discount midpoint depends on the active session's available range. Using a completed future session high/low in an earlier session would leak information. Session-routed fields can be neutral or unavailable depending on whether the context range exists; their companion active/validity fields preserve that distinction.

### Failure modes

- Using the source candle timestamp as the order-block availability time exposes the zone before the displacement confirms it.
- Using an unshifted swing level can let the current bar confirm and break the same level.
- Assuming a zone remains active indefinitely ignores its maximum age and close-through invalidation.
- Treating a retest intersection as a confirmed retest ignores the later close condition.
- Treating premium/discount as a universal market law overstates a session-specific feature definition.
- Passing raw absolute levels into the model sequence can bypass the schema's raw-price exclusion contract.

## Worked example

The Tier A notebook builds a fixed synthetic bar frame and calls both feature functions. It checks stable indexes, required output columns, and mutually exclusive midpoint flags. The example does not claim that a synthetic zone or range is tradable.

```{toctree}
:hidden:

examples/order-blocks-and-premium-discount
```

## Tasks

- [Add a feature](../../how-to/add_feature.md) and record its time-of-availability and model-facing columns.
- [Review the feature catalog](../../reference/feature_catalog.md) before changing selected columns.
- Use the [swings and liquidity guide](swings-liquidity-smt-po3-fvg-ifvg.md) for the upstream confirmed-level contract.
- Consult [risk and execution reference](../../reference/risk_and_execution.md) for downstream order behavior; this page does not define execution.

## Contract

| Item | Contract | Source |
|---|---|---|
| Required bars | Open, high, low, close on a chronological index | `features/context/order_blocks.py::_build_order_block_features` |
| Bullish zone | Last bearish candle before qualifying close-through of prior swing high | `features/context/order_blocks.py::_build_order_block_features` |
| Bearish zone | Last bullish candle before qualifying close-through of prior swing low | `features/context/order_blocks.py::_build_order_block_features` |
| Zone bounds | Source candle low and high | `features/context/order_blocks.py::_build_order_block_features` |
| Zone expiry | Maximum age and close-through invalidation | `features/context/order_blocks.py::_build_order_block_features` |
| Retest ledger | Optional per-zone diagnostic events alongside scalar output | `build_order_block_features_with_event_ledger` |
| PD session range | London: Asia plus running London; NY: completed Asia and London; Asia: prior day | `features/context/premium_discount.py::build_pd_context_features` |
| Model-facing PD | Flags and ATR distances separated from raw levels | `features/context/premium_discount.py::PD_CONTEXT_FEATURE_COLUMNS` |

## Verify

- `tests/unit/features/test_order_blocks.py` covers zone lifecycle and retest behavior.
- `tests/unit/features/test_session_ohlc.py` covers session routing and range semantics.
- `tests/unit/features/test_structure.py` covers upstream causal swing-level behavior.
- Research evidence: no controlled result for order-block or PD predictive value is claimed; it is **not measured** here.

## Limits and common mistakes

- `impulse_atr`, search span, swing period, and zone age are implementation parameters, not empirical proof of efficacy.
- A deterministic unit example does not measure hit rate or transaction costs.
- The scalar order-block view reports the latest-zone feature projection; overlapping-zone analysis requires the event ledger.
- Session definitions depend on the configured broker timezone and current session helper.
- Midpoint flags are context features, not entry or risk approvals.

## Change checklist

Before changing these features, follow the source candle, confirmation row, active zone, and consumer column through the feature builder. Then compare raw diagnostic values with the selected observation schema.

- Check the swing source and one-row shift before altering close-through rules.
- Test both bullish and bearish branches, invalidation, expiry, and a retest that confirms only on a later row.
- Test session boundaries and missing-range behavior for the PD function.
- Check that raw levels remain excluded from normalized sequence observations.
- Update feature cache identity when parameters, columns, or event timing change.
- Do not attach market-performance claims unless a separate registered study supplies reproducible evidence.

## Review procedure

Review the order-block and premium/discount paths as separate feature contracts;
they share context but do not share a single zone or session definition.

1. Start from the confirmed swing level used by the close-through check. Confirm
   that the feature does not use an unconfirmed pivot or a same-row level.
2. Trace the impulse threshold and search window to their parameters. Check the
   last opposing candle selection and verify the returned zone uses that candle's
   low/high bounds, not a later displacement candle's range.
3. Review activation, invalidation, maximum age, and retest with independent
   cases. Retest status should follow the zone lifecycle and occur after zone
   creation; it should not be inferred from a current-row overlap alone.
4. If a consumer needs to reason about multiple concurrent zones, inspect the
   event-ledger API and its event identities. Scalar outputs are a compact latest
   zone view and cannot represent every overlapping zone.
5. For premium/discount, verify the timestamp timezone and the configured
   session boundaries before interpreting any range. Session routing determines
   which prior or running ranges are eligible at each row.
6. Check the Asia, London, and New York branches independently, including rows
   at each boundary and periods where a required prior range is missing.
7. Compare raw levels with model-facing flags and ATR distances. Raw diagnostic
   levels are intentionally kept apart from the selected feature columns.
8. Confirm the feature builder's session-eligibility mask does not remove bars
   from the feature dataset. Eligibility and feature continuity are distinct.
9. Where fitted normalization is involved downstream, verify fitting uses only
   training rows and later rows reuse the last training state.

These checks establish implementation behavior for the exercised configuration.
They do not estimate zone reaction rates, trade profitability, or sensitivity to
broker feeds. Those outcomes remain **not measured** without registered studies
and reproducible run artifacts.

Record the resolved timezone, session parameters, ATR source, feature version, and
selected model columns when capturing an implementation example. For data-quality
review, report missing bars and timestamp gaps separately from detector outputs;
a quiet or empty range may reflect the input feed rather than a pattern absence.
Use only chronological bars and preserve the full feature index when applying
session eligibility downstream. Compare the model-facing columns against their
declared catalog entries before interpreting a model observation.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
