from __future__ import annotations

import pandas as pd
import pytest


def test_interactive_baseline_comparison_normalizes_each_strategy_and_saves_html(
    tmp_path,
) -> None:
    pytest.importorskip("plotly")
    from evaluation.plotting.interactive_comparison import plot_baseline_comparison

    index = pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC")
    equity = {
        "strategy_a": pd.Series([100.0, 110.0, 90.0], index=index),
        "strategy_b": pd.Series([200.0, 180.0, 220.0], index=index),
    }
    destination = tmp_path / "reports" / "comparison.html"

    figure = plot_baseline_comparison(equity, out_path=destination)

    assert [trace.name for trace in figure.data] == ["strategy_a", "strategy_b"]
    assert list(figure.data[0].y) == pytest.approx([0.0, 10.0, -10.0])
    assert list(figure.data[1].y) == pytest.approx([0.0, -10.0, 10.0])
    assert figure.layout.yaxis.title.text == "Return (%)"
    assert destination.is_file()
    assert destination.stat().st_size > 0
