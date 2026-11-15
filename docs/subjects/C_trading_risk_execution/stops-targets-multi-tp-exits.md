# Stops, targets, multi-TP exits

**Status:** draft
**Use this when:** You need to trace order geometry from a selected entry through partial and final exits.

## Summary and use this when

An entry has a direction, a stop, and one or more targets. The order layer constructs and validates levels; the position layer tracks target slots and remaining size; the environment applies fills. The notebook demonstrates deterministic selection and geometry, not a trade result. Sources: `trading/orders/entries.py`, `trading/orders/selection.py`, `trading/positions/multi_tp.py`, `simulation/environment/protective_level_runtime.py`.

- Use this guide when investigating rejected stop/target geometry.
- Use it when interpreting TP slot identity and a partial close.
- Use the [action schema guide](../B_market_structure_setups/action-schemas-and-parameterization.md) for serialized policy coordinates.
- Use the [subject reference](../../reference/subjects/stops-targets-multi-tp-exits.md) for exact fields.

## Key terms

- [Trade setup](../../glossary.md)
- [Action schema](../../glossary.md)
- [Risk budget](../../glossary.md)
- [R multiple](../../glossary.md)

## Explanation

### Constructing a stop

`compute_sl_tp_long` requires a swing low strictly below entry and subtracts a price-point buffer. `compute_sl_tp_short` requires a swing high strictly above entry and adds that buffer. Each computes a target from the entry-to-stop distance and requested reward/risk ratio. Source: `trading/risk/sizing.py::compute_sl_tp_long`, `compute_sl_tp_short`; test: `tests/unit/trading/test_risk.py`.

The structure path can select a stop reference from a menu of eligible candidates. Candidate names and prices are retained so a rejection has provenance; a stop is not made valid by silently moving it across the entry. Source: `trading/orders/stops.py::stop_menu`, `filter_sl_candidates`; `trading/orders/entries.py::place_strategy_order`.

A target menu is assembled from available level families and collapsed to usable prices. `validate_tp_levels` enforces side and ordering: active long targets ascend at or above entry; active short targets descend at or below entry; the stop must remain on the adverse side. Source: `trading/orders/targets.py::target_menu`, `collapse_levels`; `trading/orders/selection.py::validate_tp_levels`.

### Selecting target slots

`decode_tp_selections` maps each raw selection into TP1, TP2, or TP3 without changing the slot's identity. With a nonempty menu, all-disabled input falls back to menu index zero in TP3. If TP3 is disabled but another slot is valid, the furthest valid selection is promoted; duplicate or out-of-order nearer slots are disabled. Source: `trading/orders/selection.py::decode_tp_selections`; test: `tests/unit/simulation/test_environment/test_tp_action_decode.py`.

`decode_tp_fractions` turns two logits and an implicit zero into three nonnegative fractions. When active slots are supplied, disabled slots are omitted and the remaining fractions are renormalized. The tuple length must be three. Source: `trading/orders/selection.py::decode_tp_fractions`; test: `tests/unit/simulation/test_environment/test_tp_action_contracts.py`.

The TP mode decoder has fixed, breakeven, and trailing outcomes. A value inside its neutral defer band uses the configured default and records that the action did not explicitly override it. Source: `trading/orders/selection.py::decode_tp_mode`; test: `tests/unit/simulation/test_environment/test_tp_mode_state.py`.

### Closing a position

`target_close_size` uses the initial position size and active-slot fractions, caps a leg at remaining size, and closes the full residual on the last target when no EMA runner is configured. With a positive runner fraction, the final close is capped to leave the runner when that calculation produces a positive close size; if it produces zero, the function falls back to closing the full remainder. Source: `trading/positions/multi_tp.py::target_close_size`; test: `tests/unit/trading/test_multi_tp.py`.

`reorder_remaining_targets` disables invalid or duplicate remaining levels after position changes; it does not fabricate a replacement target. The position retains hit-mask and original-size fields to prevent a later partial from being sized against the already reduced remainder. Source: `trading/positions/multi_tp.py::reorder_remaining_targets`; `trading/execution/broker.py::Position`.

At an ambiguous OHLC bar that spans a stop and target, environment tests assert stop-first treatment. A gap through a stop can fill at the open or worse. Those are simulator assumptions, not observed broker fills. Source: `simulation/environment/protective_level_runtime.py`; tests: `tests/unit/simulation/test_environment/test_tp_execution.py::test_ambiguous_ohlc_uses_stop_before_any_target`, `test_gap_through_stop_fills_at_open_or_worse`.

### Why these boundaries matter

Order construction answers which levels are proposed. Validation answers whether the proposed geometry is coherent. Position state answers how much remains after a fill. Execution answers the actual fill price and time. Mixing those stages can make a target look valid despite an impossible stop or count a partial position as multiple trades. Sources: `trading/orders/entries.py`, `trading/orders/selection.py`, `trading/positions/multi_tp.py`, `simulation/environment/trade_accounting_runtime.py`.

## Worked example

The paired Tier A notebook uses fixed prices. It checks long and short stop/target calculations, ordered TP slots, fraction normalization, and a rejected crossed level. It does not use market feeds or estimate profitability.

```{toctree}
:hidden:

examples/stops-targets-multi-tp-exits
```

## Tasks

- Use [add action schema](../../how-to/add_action_schema.md) before changing action coordinates.
- Use [schema version change](../../how-to/schema_version_change.md) before changing persisted TP slot meaning.
- Compare selected levels with [trade setup](../B_market_structure_setups/trade-setups.md) provenance.
- Read the [risk and execution reference](../../reference/risk_and_execution.md) when sizing or fill price changes.

## Contract

| Item | Contract | Source |
|---|---|---|
| Long geometry | Swing low below entry; stop below low by buffer | `trading/risk/sizing.py::compute_sl_tp_long` |
| Short geometry | Swing high above entry; stop above high by buffer | `trading/risk/sizing.py::compute_sl_tp_short` |
| Target ordering | Active levels progress away from entry | `trading/orders/selection.py::validate_tp_levels` |
| Slot selection | TP1/TP2/TP3 identity survives repair | `trading/orders/selection.py::decode_tp_selections` |
| Fractions | Active fractions renormalize to one | `trading/orders/selection.py::decode_tp_fractions` |
| Partial size | Computed from initial size, capped by remainder | `trading/positions/multi_tp.py::target_close_size` |
| Runner | Positive final close is capped to retain the runner; zero computed close falls back to full remainder | `trading/positions/multi_tp.py::target_close_size` |
| Hit state | `tp_hit_mask` marks already executed slots | `trading/execution/broker.py::Position` |

## Verify

- `tests/unit/trading/test_risk.py` covers structural stop/target math and invalid geometry.
- `tests/unit/trading/test_multi_tp.py` covers partial sizing and target reordering.
- `tests/unit/simulation/test_environment/test_tp_action_decode.py` covers slot decoding.
- `tests/unit/simulation/test_environment/test_tp_execution.py` covers actual environment target/stop ordering and partial fills.
- Strategy profitability, stop quality, target hit rates, and broker parity are **not measured** here.

## Limits and common mistakes

- A computed target is a proposal, not a promise that the next quote reaches it.
- A slot index is a menu selection, not a price; resolve against the same menu version.
- The fraction tuple describes active legs, not always all three slots.
- An EMA runner can leave size after the last structural TP.
- An OHLC bar cannot reveal the intrabar order of stop and target touches.
- Spread, slippage, and commission change realized R; use actual fill records.
- Do not compare a reported R multiple with a target's nominal RR as if they were equal.

## Review procedure

1. Record entry time, direction, entry quote, and candidate ID.
2. Inspect stop candidate source, reference price, and buffer units.
3. Confirm the stop is adverse to entry before computing lot size.
4. Record target menu entries and their source levels.
5. Decode each TP slot using the exact action schema and menu size.
6. Check disabled-slot fallback and duplicate/order repair.
7. Validate resulting target prices against entry and stop.
8. Save active fractions with their slot mapping.
9. On each fill, inspect position ID, hit mask, initial size, and remaining size.
10. Check whether an EMA runner intentionally remains.
11. Compare quote source and actual fill price with nominal level.
12. Treat ambiguous bar extrema under the documented stop-first simulator rule.
13. Count a sequence of partial fills as one position lifecycle.
14. Keep any rejected or incomplete order in the audit record.

A minimal defect report should contain the exact menu, raw slot actions, decoded slots, target levels, entry/stop prices, active fractions, position size before/after, and fill source. Record source revision and action schema version. A synthetic notebook check establishes only deterministic contract behavior; OOS trading quality is **not measured**.

## Diagnostic cases

The following cases locate the contract boundary to inspect. They are software checks, not evidence of market outcomes.

| Case | Expected inspection result | Source |
|---|---|---|
| Long swing at entry | Reject geometry before sizing | `trading/risk/sizing.py` |
| Short swing below entry | Reject geometry before sizing | `trading/risk/sizing.py` |
| Negative target slot | Disable that slot | `trading/orders/selection.py` |
| All slots disabled | Use nearest menu target in TP3 | `trading/orders/selection.py` |
| TP3 disabled with TP2 active | Promote the furthest valid slot | `trading/orders/selection.py` |
| Two slots choose one target | Disable duplicate nearer slot | `trading/orders/selection.py` |
| TP1 index beyond TP2 | Disable out-of-order nearer slot | `trading/orders/selection.py` |
| No target menu | Return all slots disabled | `trading/orders/selection.py` |
| Active fraction mask | Renormalize remaining fractions | `trading/orders/selection.py` |
| Invalid active-slot length | Raise a value error | `trading/orders/selection.py` |
| Long stop above entry | Reject level validation | `trading/orders/selection.py` |
| Short stop below entry | Reject level validation | `trading/orders/selection.py` |
| Long targets descending | Reject level validation | `trading/orders/selection.py` |
| Short targets ascending | Reject level validation | `trading/orders/selection.py` |
| Final target without runner | Close residual position size | `trading/positions/multi_tp.py` |
| Partial close after earlier TP | Use original size for fraction | `trading/positions/multi_tp.py` |
| Remaining target crosses entry | Disable that target | `trading/positions/multi_tp.py` |
| Remaining targets duplicate | Disable invalid later target | `trading/positions/multi_tp.py` |
| Bar touches stop and TP | Treat stop as first in simulator test | `tests/unit/simulation/test_environment/test_tp_execution.py` |
| Gap through stop | Use open or worse in simulator test | `tests/unit/simulation/test_environment/test_tp_execution.py` |

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `quantitative_trading_engineer`
