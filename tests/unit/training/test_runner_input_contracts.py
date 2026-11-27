"""Input validation contracts for the training runner modules."""

from __future__ import annotations

import sys

import pandas as pd
import pytest

from training.runner import baselines
from training.runner.data_stage import _clip_data_to_development_end


def test_baseline_cli_rejects_unknown_strategy_before_loading_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unsupported strategy must fail at argparse before config or data IO."""
    monkeypatch.setattr(sys, "argv", ["baselines", "--strategy", "unknown"])
    monkeypatch.setattr(
        baselines,
        "load_config",
        lambda *_args, **_kwargs: pytest.fail("invalid CLI input must not load config"),
    )

    with pytest.raises(SystemExit) as exc_info:
        baselines.main()

    assert exc_info.value.code == 2


def test_development_data_clipping_rejects_non_datetime_bar_index() -> None:
    """Clipping fails closed when a source frame cannot be date-split."""
    bars = pd.DataFrame({"close": [100.0, 101.0]}, index=[0, 1])

    with pytest.raises(TypeError, match="ES M1 bars require a DatetimeIndex"):
        _clip_data_to_development_end(
            {"ES": {"M1": bars}},
            train_end="2025-12-31",
        )


def test_development_data_clipping_keeps_inclusive_cutoff_per_symbol_and_timeframe() -> None:
    index = pd.date_range("2025-12-30", periods=4, freq="D")
    primary = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0]}, index=index)
    secondary = pd.DataFrame({"close": [20.0, 21.0, 22.0, 23.0]}, index=index)

    clipped = _clip_data_to_development_end(
        {"ES": {"M1": primary, "H1": secondary}, "NQ": {"M1": secondary}},
        train_end="2025-12-31",
    )

    assert set(clipped) == {"ES", "NQ"}
    assert list(clipped["ES"]) == ["M1", "H1"]
    for symbol_frames in clipped.values():
        for bars in symbol_frames.values():
            assert bars.index.equals(index[:2])
