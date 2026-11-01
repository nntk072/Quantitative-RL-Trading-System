# Features · `po3.fvg`

This page contains 1 public callable records owned by `features.po3.fvg`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_fvg_zone_features`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.fvg`

**Purpose:** Model-facing FVG zone features for one timeframe's own bars.

**Exact API:** {py:obj}`features.po3.fvg.build_fvg_zone_features` · **Source:** [features/po3/fvg.py:17](../../../../features/po3/fvg.py#L17)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  fvg_config: Fvg config used by the operation described above.
  max_zone_bars: Market bar or price data used for model-facing FVG zone features for one timeframe's own bars.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_fvg_zone_features``.
  ```

**Observed usage:**

1. [test fixture: `test_fvg_reaction_buffer_is_optional`](../../../../tests/unit/features/test_po3_state.py#L357)

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

2. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L318)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                if buffer_enabled
                else 0.0
            )
            for tf in fvg_tfs:
                tf_bars = primary_tf_bars(str(tf))
                fvg_blocks[str(tf)] = build_fvg_zone_features(
                    tf_bars,
                    fvg_config=FVGConfig(
                        reaction_buffer_fraction=reaction_buffer_fraction,
                        reaction_buffer_enabled=buffer_enabled,
                    ),
                )
            feat = align_blocks(feat, fvg_blocks)
            # Zone prices and the retest flag must stay raw. The distance
            # columns above are normalised with the rest of the matrix.
            feat, _fvg_raw = split_raw_fvg_features(feat)

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
