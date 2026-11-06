# Features · `po3.fvg`

This page contains 1 public callable records owned by `features.po3.fvg`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_fvg_zone_features`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.fvg`

**Purpose:** Build causal scalar FVG zone features for one timeframe's own bars.

**Exact API:** {py:obj}`features.po3.fvg.build_fvg_zone_features` · **Source:** [features/po3/fvg.py:28](../../../../features/po3/fvg.py#L28)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: OHLC bars indexed by their decision timestamps.
  fvg_config: Optional gap and retest configuration.
  max_zone_bars: Maximum active lifetime of each FVG zone.
  ```

- **Returns:**

  ```text
  One row per input bar with scalar FVG-zone features.
  ```

**Observed usage:**

1. [test fixture: `test_overlapping_fvg_retests_project_the_newest_zone_identity_causally`](../../../../tests/unit/features/test_po3_state.py#L385)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                (104.0, 99.5, 101.5),  # both zones collect a retest wick
                (105.0, 104.5, 104.8),  # confirms both on one row
            ]
        )

        full = build_fvg_zone_features(bars)
        prefix = build_fvg_zone_features(bars.iloc[:6])

        assert full["fvg_retest_bull"].iloc[6] == 1.0
        assert full["fvg_bull_retest_confirmed_at_time_ns"].iloc[6] == bars.index[6].value
        assert full["fvg_bull_retest_origin_time_ns"].iloc[6] == bars.index[3].value
# … caller assertions omitted …
```

2. [test fixture: `test_fvg_reaction_buffer_is_optional`](../../../../tests/unit/features/test_po3_state.py#L450)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                (101.0, 100.91, 100.92),
            ]
        )
        bars.loc[bars.index[5], "open"] = 100.8
        bars.loc[bars.index[6], "open"] = 100.91
        enabled = build_fvg_zone_features(
            bars,
            fvg_config=FVGConfig(reaction_buffer_fraction=0.1, reaction_buffer_enabled=True),
        )
        disabled = build_fvg_zone_features(
            bars,
            fvg_config=FVGConfig(reaction_buffer_fraction=0.1, reaction_buffer_enabled=False),
        )
        lower = build_fvg_zone_features(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
