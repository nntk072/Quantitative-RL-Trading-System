"""Regression tests for the reusable causal availability figure's data."""

from __future__ import annotations

import pandas as pd
from scripts.research.analysis.features.plot_feature_availability_example import (
    build_synthetic_alignment_example,
)


def test_synthetic_figure_data_exposes_htf_event_only_at_configured_close() -> None:
    example = build_synthetic_alignment_example()
    event_open = pd.Timestamp("2025-01-01 00:10", tz="UTC")
    event_close = pd.Timestamp("2025-01-01 00:15", tz="UTC")

    assert (
        example.loc[: event_open - pd.Timedelta(minutes=1), "causal_close_available"].sum() == 0.0
    )
    assert example.loc[event_open, "naive_open_available"] == 1.0
    assert example.loc[event_open, "causal_close_available"] == 0.0
    assert example.loc[event_close, "causal_close_available"] == 1.0
