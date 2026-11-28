# Swings, liquidity, SMT, PO3, FVG, and IFVG

**Status:** draft
**Use this when:** You need to understand confirmed market-structure events or how the feature pipeline turns them into causal context columns.

## Summary and use this when

This subject groups confirmed swings, liquidity sweeps, paired-symbol SMT, PO3 state, and fair-value-gap lifecycles. These are deterministic feature definitions in this repository. Their names do not establish a market mechanism or profitable signal.

- Use this guide when tracing a structure or gap feature from bars to an observation.
- Use it when checking event timestamps, confirmation delay, or feature prefixes.
- Use the trade-setup guide for the catalog that consumes entry-idea features.

## Key terms

- [Availability time](../../glossary.md)
- [SMT](../../glossary.md)
- [PO3](../../glossary.md)
- [FVG](../../glossary.md)
- [IFVG](../../glossary.md)

## Explanation

### The rule

`features/technical/swings.py::detect_pivots` identifies a local high or low only after the configured number of right-side bars is present. It writes the event on the confirmation row and retains the original pivot location separately. A future extreme is therefore not exposed at the pivot row.

`detect_swings` consumes those confirmed pivot events. It can replace an unaccepted candidate with a more extreme candidate and accepts a swing after close reverses by `atr_mult * ATR`, with ATR frozen at the candidate's confirmation. If ATR is unavailable, the candidate is accepted on its confirmation row. The output includes events and forward-filled levels.

`features/context/liquidity.py::detect_liquidity_sweeps` compares the current bar with the most recently confirmed swing level shifted by one row. A fresh take within `max_sweep_distance_atr * ATR` emits a sweep event; a deeper move is treated as a breakout for this detector. The active sweep records its level, age, wick, and whether a close reclaims the level. `detect_liquidity_sweeps_retained` provides a separate event view across retained levels.

`features/context/smt.py::smt_divergence` detects confirmed pivots on both source indexes. A secondary-symbol event is projected to the first primary row at or after its confirmation timestamp. It does not place that event on an earlier primary row when timestamp coverage differs.

`features/po3/po3_phase_state.py::build_po3_state` starts a manipulation state from a qualified sweep and confirms a distribution direction when the close breaks the running manipulation extreme from the prior bar. A new same-side sweep re-arms the state; an opposite-side sweep changes the active side.

`features/po3/fvg_detection.py::detect_fvg` uses a three-bar imbalance and emits it on bar three. `features/po3/ifvg_detection.py::detect_ifvg_confirmation` tracks active gaps; confirmation requires a pass through the zone and a later close beyond the most extreme passing wick, with an optional configured buffer.

### Why it works this way

A pivot's final right-side comparison is unavailable until those bars close. Stamping an event on the pivot bar would move information backward. The confirmation row and original location are kept as separate fields so consumers can distinguish when the feature became knowable from where the pattern originated.

The sweep detector uses the prior row's confirmed level, which avoids using a swing first confirmed by the current bar to classify that same bar. SMT keeps each instrument's observed source timestamps for pivot detection; forward-filled closes are used only for aligned close-derived context.

PO3 and IFVG are state machines rather than single-row labels. Their state records the events and price boundaries required to determine when the phase changes or a zone becomes confirmed. The scalar feature view selects one current event; diagnostic ledgers can preserve additional overlapping zone events without changing that scalar output.

### Failure modes

- Reading a pivot's stored location as its availability timestamp makes a confirmed event appear too early.
- Using current-row swing levels instead of the shifted level can create a same-bar look-ahead path in sweep detection.
- Forward-filled secondary OHLC rows are not observed secondary bars and must not count as new pivot observations.
- A breakout farther than the configured ATR cap is not a sweep under this detector's definition.
- Treating a raw FVG as an IFVG skips the required later pass and confirmation sequence.
- Treating a PO3 phase or gap label as a validated trade signal exceeds the available evidence.

## Worked example

The Tier A notebook uses a short synthetic OHLC sequence. It checks that a fractal pivot is reported on its confirmation row and that a three-bar gap is emitted on bar three. It uses no market feed and makes no prediction or performance claim.

```{toctree}
:hidden:

examples/swings-liquidity-smt-po3-fvg-ifvg
```

## Tasks

- Keep each feature's event time distinct from its source location.
- [Build a feature cache](../../how-to/build_feature_cache.md) after changing output semantics or source-time inputs.
- Use the [feature catalog](../../reference/feature_catalog.md) to inspect configured output families.
- Use the [causality and normalization guide](../A_data_features/feature-causality-and-normalization.md) for train-only fitting and higher-timeframe availability.

## Contract

| Item | Contract | Source |
|---|---|---|
| Pivot event | Event emitted after `right` confirmation bars | `features/technical/swings.py::detect_pivots` |
| Accepted swing | Candidate close-reversal threshold uses ATR frozen at confirmation | `features/technical/swings.py::detect_swings` |
| Sweep level | Previously confirmed swing level, shifted one row | `features/context/liquidity.py::detect_liquidity_sweeps` |
| Sweep distance | Fresh take must not exceed configured ATR distance | `features/context/liquidity.py::detect_liquidity_sweeps` |
| SMT pairing | Secondary confirmation projects to first primary row at/after its time | `features/context/smt.py::smt_divergence` |
| PO3 transition | Sweep starts manipulation; prior-extreme close confirms distribution | `features/po3/po3_phase_state.py::build_po3_state` |
| FVG | Three-bar high/low imbalance, emitted on third bar | `features/po3/fvg_detection.py::detect_fvg` |
| IFVG | Pass through zone followed by later close beyond passing wick | `features/po3/ifvg_detection.py::detect_ifvg_confirmation` |

Exact defaults and feature inclusion are controlled by the implementation and resolved configuration. The feature catalog describes the selected model columns.

## Verify

- `tests/unit/features/test_pivots_swings.py` covers pivot confirmation and accepted swing behavior.
- `tests/unit/features/test_liquidity.py` covers fresh takes, reclaim, and causal level use.
- `tests/unit/features/test_smt.py` covers paired-symbol divergence.
- `tests/unit/features/test_po3_ifvg_state.py` covers PO3/IFVG state transitions.
- Research evidence: no R1–R4 market-performance result is asserted by this guide; predictive value is **not measured** here.

## Limits and common mistakes

- Parameter values change the operational definition; they do not follow from the pattern name.
- Synthetic notebook checks cover a few software examples, not every timeframe or feed boundary.
- Same-row overlapping zones may be summarized by scalar outputs. Use the event-ledger APIs when the analysis needs per-zone provenance.
- A feature prefix test establishes a tested causal software property, not market predictiveness.
- Keep source timestamps, confirmation timestamps, configuration, and generated cache identity together when documenting a real run.

## Change checklist

When changing one detector, inspect the feature builder that selects and aligns its output, the observation schema that carries it, and the exact source-time fields used by any downstream candidate identity.

- Add a boundary case for the first possible confirmation row and the last row lacking enough right-side bars.
- Add a future-append test when a new state transition could use later rows.
- Check the M1 and higher-timeframe paths separately; availability after source close is part of the contract.
- Preserve the distinction between a scalar latest-zone projection and a per-zone diagnostic ledger.
- Update the feature cache version and content hash inputs when output meaning or source identity changes.
- Keep a no-evidence statement when no controlled research artifact supports a performance claim.

## Review procedure

Use this sequence when a change touches a detector or its emitted timestamp.
It is intended for code review and documentation maintenance, not for deciding
whether a pattern should be traded.

1. Identify the earliest input row each output can depend on. For pivots, this
   includes the right-side confirmation bars; for accepted swings, include the
   reversal close and the ATR value frozen at that confirmation.
2. Write down both the source location and the event/availability row. A pivot
   can refer to an earlier extreme while becoming knowable only later.
3. Verify that consumers see only the confirmed level. Liquidity sweeps shift
   the structure level before comparison, so a same-row newly confirmed level
   cannot retroactively create a sweep.
4. Exercise sweep distance and reclaim separately. A wick beyond the level is
   not sufficient if the penetration exceeds its configured ATR bound, and a
   reclaim is a distinct output from the initial take.
5. For SMT, inspect timestamps on both symbol indexes. A secondary event maps
   forward to the first primary observation at or after confirmation; unmatched
   secondary observations do not justify backfilling a primary event.
6. For PO3, verify the state transition sequence: qualified sweep, manipulation
   state, then a close through the prior running extreme for distribution.
   Confirm that a later sweep re-arms the state rather than rewriting history.
7. For FVG and IFVG, use small hand-checked bars to prove the three-bar gap,
   zone bounds, pass-through, and the later close beyond the passing wick.
8. Append future bars to a prefix and compare earlier outputs. This checks a
   software causality property for the selected fixture only; it says nothing
   about the market value of the detector.
9. Keep fixture expectations and configuration explicit. Defaults and feature
   inclusion can change independently of the detector's algorithm.

When reporting results, separate detector correctness from event frequency,
fill feasibility, slippage, and net performance. The latter are not measured
by these source contracts or the bundled synthetic example.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `data_scientist_engineer`
