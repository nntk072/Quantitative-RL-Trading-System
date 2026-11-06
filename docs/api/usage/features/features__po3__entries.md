# Features · `po3.entries`

This page contains 1 public callable records owned by `features.po3.entries`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_po3_phase_features`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.entries`

**Purpose:** PO3 (Power of 3) daily-cycle phase tag, causally time-derived.

**Exact API:** {py:obj}`features.po3.entries.build_po3_phase_features` · **Source:** [features/po3/entries.py:11](../../../../features/po3/entries.py#L11)

**Inputs and outputs:**

- **Args:**

  ```text
  index: Position or label identifying the requested item.
  session_start: Text or path value identifying the session start.
  session_end: Text or path value identifying the session end.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_po3_phase_features``.
  ```

**Observed usage:**

1. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L444)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    _fvg_raw = pd.DataFrame(index=primary.index)
    if feat_cfg is not None:
        # PO3 phase tag: time-derived, identical across TFs once aligned.
        if bool(getattr(feat_cfg, "include_po3", False)):
            session = OmegaConf.select(cfg, "session") if cfg is not None else None
            po3 = build_po3_phase_features(
                pd.DatetimeIndex(primary.index),
                session_start=str(session.get("start", "16:30")) if session else "16:30",
                session_end=str(session.get("end", "23:00")) if session else "23:00",
            )
            feat = pd.concat([feat, po3], axis=1)

            # FVG zones cover the primary timeframe and configured higher timeframes.
            # build_fvg_zone_features is TF-agnostic, so this is purely what goes
            # into the loop: ["M1"] + htf_timeframes (config-overridable via
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
