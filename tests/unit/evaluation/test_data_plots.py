"""Smoke tests for data/EDA trade_setup charts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from evaluation.plotting import data_plots
from evaluation.plotting.data import exploration as data_exploration
from evaluation.plotting.data_plots import (
    plot_feature_histograms,
    plot_log_return_dist,
    plot_session_profile,
    plot_signals_for_day,
    write_data_eda,
)


def _ny_bars(n: int = 500, *, volume: bool = True, tickvol: bool = False) -> pd.DataFrame:
    idx = pd.date_range("2025-01-02 16:30", periods=n, freq="1min")
    rng = np.random.default_rng(0)
    close = 20000.0 + np.cumsum(rng.normal(0, 1, n))
    data: dict[str, object] = {
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
    }
    if volume:
        data["volume"] = rng.integers(10, 100, n)
    if tickvol:
        data["tickvol"] = rng.integers(10, 100, n)
    return pd.DataFrame(data, index=idx)


def test_write_data_eda_creates_core_pngs(tmp_path):
    bars = _ny_bars()
    rng = np.random.default_rng(0)
    features = pd.DataFrame(
        {
            "rsi": rng.uniform(20, 80, 500),
            "atr": rng.uniform(1, 5, 500),
            "entry_long": rng.integers(0, 2, 500),
            "entry_short": rng.integers(0, 2, 500),
            "price_in_ifvg_bull": rng.integers(0, 2, 500),
        },
        index=bars.index,
    )
    out = write_data_eda(
        tmp_path / "data",
        bars,
        features,
        train_end="2025-01-02 20:00",
        test_start="2025-01-02 20:01",
        dpi=72,
        po3_sample=False,
    )
    for name in (
        "coverage_calendar.png",
        "log_return_dist.png",
        "session_profile.png",
        "train_test_split.png",
        "feature_histograms.png",
        "signal_counts.png",
    ):
        path = out / name
        assert path.exists(), name
        assert path.stat().st_size > 0, name
    # Per-day signal folder (one NY calendar day in this fixture).
    sig_dir = out / "signals_by_day"
    assert sig_dir.is_dir()
    assert any(sig_dir.glob("*.png"))


def test_session_profile_tickvol_panel(tmp_path):
    bars = _ny_bars(volume=False, tickvol=True)
    fig = plot_session_profile(bars, out_path=tmp_path / "sess.png", dpi=72)
    assert len(fig.axes) == 2


def test_session_profile_no_volume_single_panel(tmp_path):
    bars = _ny_bars(volume=False, tickvol=False)
    fig = plot_session_profile(bars, out_path=tmp_path / "sess.png", dpi=72)
    assert len(fig.axes) == 1


def test_session_profile_zero_volume_uses_tickvol(tmp_path):
    bars = _ny_bars(volume=True, tickvol=True)
    bars["volume"] = 0
    fig = plot_session_profile(bars, out_path=tmp_path / "sess.png", dpi=72)
    assert len(fig.axes) == 2


def test_session_profile_with_no_ny_bars_shows_empty_state_and_saves(tmp_path):
    bars = _ny_bars(n=3)
    bars.index = pd.date_range("2025-01-02 00:00", periods=3, freq="min")

    fig = plot_session_profile(bars, out_path=tmp_path / "off-session.png", dpi=72)

    assert len(fig.axes) == 1
    assert any(text.get_text() == "No NY bars" for text in fig.axes[0].texts)
    assert (tmp_path / "off-session.png").stat().st_size > 0


def test_log_return_plot_handles_constant_and_nonpositive_close_series():
    index = pd.date_range("2025-01-02 16:30", periods=3, freq="min")
    constant = plot_log_return_dist(pd.DataFrame({"close": [100.0] * 3}, index=index))
    assert len(constant.axes[0].lines) == 1
    assert np.isfinite(constant.axes[0].lines[0].get_ydata()).all()

    invalid = plot_log_return_dist(pd.DataFrame({"close": [100.0, 0.0, -1.0]}, index=index))
    assert any(text.get_text() == "No returns" for text in invalid.axes[0].texts)
    constant.clear()
    invalid.clear()


def test_constant_feature_histogram_uses_fallback_range_without_failure():
    index = pd.date_range("2025-01-02 16:30", periods=3, freq="min")
    fig = plot_feature_histograms(pd.DataFrame({"rsi": [50.0, 50.0, 50.0]}, index=index))

    assert "rsi" in fig.axes[0].get_title()
    assert "n=3" in fig.axes[0].get_title()
    assert fig.axes[0].patches
    fig.clear()


def test_empty_eda_input_creates_destination_without_partial_plot_files(tmp_path):
    destination = tmp_path / "empty-eda"

    out = write_data_eda(destination, pd.DataFrame(columns=["close"]))

    assert out == destination
    assert out.is_dir()
    assert list(out.iterdir()) == []


def test_daily_signal_writer_continues_after_one_day_plot_failure(tmp_path, monkeypatch, caplog):
    index = pd.date_range("2025-01-02 16:30", periods=2, freq="1D")
    features = pd.DataFrame({"entry_long": [1, 1]}, index=index)
    calls: list[pd.Timestamp] = []

    def fail_plot(_features, day, **_kwargs):
        calls.append(pd.Timestamp(day))
        raise RuntimeError("renderer unavailable")

    monkeypatch.setattr(data_exploration, "plot_signals_for_day", fail_plot)
    output = tmp_path / "daily-signals"

    data_plots._write_signals_by_day(features, output, dpi=72)

    assert output.is_dir()
    assert len(calls) == 2
    assert "renderer unavailable" in caplog.text


def test_signal_day_with_no_matching_session_bars_renders_empty_state():
    index = pd.date_range("2025-01-02 00:00", periods=3, freq="min")
    features = pd.DataFrame({"entry_long": [0, 1, 0]}, index=index)

    fig = plot_signals_for_day(features, pd.Timestamp("2025-01-02"))

    assert any(text.get_text() == "No NY signals" for text in fig.axes[0].texts)
    fig.clear()


def test_write_data_eda_po3_by_day(tmp_path):
    # Two NY sessions on consecutive days so by-day folders get multiple files.
    # Include pre-session bars so full-day PO3 charts have off-session candles.
    idx1 = pd.date_range("2025-01-02 10:00", periods=600, freq="1min")
    idx2 = pd.date_range("2025-01-03 10:00", periods=600, freq="1min")
    idx = idx1.append(idx2)
    rng = np.random.default_rng(1)
    close = 20000.0 + np.cumsum(rng.normal(0, 1, len(idx)))
    bars = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "tickvol": rng.integers(10, 50, len(idx)),
        },
        index=idx,
    )
    features = pd.DataFrame(
        {
            "rsi": rng.uniform(20, 80, len(idx)),
            "entry_long": rng.integers(0, 2, len(idx)),
            "entry_short": rng.integers(0, 2, len(idx)),
            "price_in_ifvg_bull": rng.integers(0, 2, len(idx)),
            "htf_fvg_bullish": rng.integers(0, 2, len(idx)),
        },
        index=idx,
    )
    out = write_data_eda(
        tmp_path / "data",
        bars,
        features,
        dpi=72,
        po3_sample=True,
    )
    assert (out / "signals_by_day").is_dir()
    assert len(list((out / "signals_by_day").glob("*.png"))) >= 2
    # PO3 sample + by-day may skip if detect_po3_entries fails on tiny data;
    # at least the sample path attempt should not crash write_data_eda.
    assert (out / "feature_histograms.png").exists()


def test_slice_calendar_day_includes_off_session_bars():
    """PO3 day charts use the full broker day, not NY-only."""
    from evaluation.plotting.data_plots import _slice_calendar_day, _slice_ny_day

    idx = pd.date_range("2025-01-02 00:00", periods=24 * 60, freq="1min", tz="Etc/GMT-3")
    close = 20000.0 + np.arange(len(idx), dtype=float)
    bars = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close},
        index=idx,
    )
    day = pd.Timestamp("2025-01-02", tz="Etc/GMT-3")
    full, _lb = _slice_calendar_day(bars, day, lookback_bars=0)
    ny, _ = _slice_ny_day(bars, day, lookback_bars=0)
    assert len(full) == 24 * 60
    assert len(ny) < len(full)
    assert full.index[0].hour == 0
    assert full.index[-1].hour == 23
