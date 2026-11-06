# Active feature event-family semantics

This packet records the current-source synthetic contract run for the event
families named in Stage D. Nine focused feature suites passed 157/157 on the
existing GH200 allocation. The tests use controlled OHLC/secondary-symbol
fixtures; they do not report market prevalence, performance, or policy value.

| Event family | Verified behavior in the focused suites |
|---|---|
| Swings and retained structure | Pivot confirmation is delayed until the required right bars; outputs are not backdated. Retained levels appear after confirmation and disappear on body close-through. Future truncation preserves earlier outputs. |
| Order blocks | Confirmation and retest require the documented later-bar sequence; same-side replacement, overlapping retests, scalar selection, and event-ledger prefix behavior are covered. |
| FVG zones | Zone formation, active bounds, retest/hold, fill invalidation, age expiry, overlap collisions, scalar origin selection, and prefix causality are exercised. |
| IFVG | Bullish and bearish close-through confirmation, source-gap identity, zone fill/expiry, later retest, collisions, and event-ledger prefix causality are exercised. |
| PO3 setup state | Sweep starts manipulation; close reclaim uses the exact swept reference; IFVG readiness requires a qualifying post-sweep source; direction reset and same-candle reclaim ordering are tested. |
| Higher-timeframe visibility | FVG/IFVG values are not exposed before their source candle closes; matched IFVG readiness and entry timing follow the configured close alignment without an added second delay. |
| Liquidity sweeps and BOS | Confirmation, reclaim separation, distance filters, continuation behavior, and future-data truncation are tested. |
| SMT | Paired swing confirmation is required; secondary observations are forward-filled without future influence; missing secondary rows do not duplicate bars or backdate confirmation. |

The exact test output and the source, test, and canonical configuration hashes
are recorded in `run_metadata.json`. Reproduce the run on the matching
architecture with:

```bash
.venv/bin/python -m pytest \
  tests/unit/features/test_pivots_swings.py \
  tests/unit/features/test_order_blocks.py \
  tests/unit/features/test_variants.py \
  tests/unit/features/test_po3_config.py \
  tests/unit/features/test_po3_state.py \
  tests/unit/features/test_po3_ifvg_state.py \
  tests/unit/features/test_po3_mtf_state.py \
  tests/unit/features/test_smt.py \
  tests/unit/features/test_liquidity.py -q
```

This closes the listed synthetic event-contract subcases for the recorded
current source snapshot. It does not close the full Stage D gate: validity and
left-padding semantics across every model tensor, training-only fitting and
cache parity still need their own acceptance evidence. It also does not show
event rates in market data or recover historical PPO decision-to-candidate
linkage.
