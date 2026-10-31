from __future__ import annotations

import pandas as pd
from scripts.research.analysis.evaluation.plot_stochastic_equity_ensemble import _align_paths


def test_align_paths_unions_timestamps_and_carries_forward_early_terminal_equity() -> None:
    start = pd.Timestamp("2025-01-01", tz="UTC")
    middle = start + pd.Timedelta(days=1)
    end = start + pd.Timedelta(days=2)
    paths = [
        pd.Series([100.0, 105.0], index=[start, middle], name="early"),
        pd.Series([100.0, 98.0, 102.0], index=[start, middle, end], name="full"),
    ]

    matrix, terminal_positions = _align_paths(paths, ["early", "full"])

    assert matrix.index.tolist() == [start, middle, end]
    assert matrix["early"].tolist() == [100.0, 105.0, 105.0]
    assert matrix["full"].tolist() == [100.0, 98.0, 102.0]
    assert terminal_positions == [2, 3]
