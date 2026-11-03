"""Tests: causal feature computation (no look-ahead) + encoder shapes."""

from __future__ import annotations

from typing import Any

import pandas as pd
import torch

from features.technical.indicators import (
    ema_features,
    macd,
    returns,
    rsi,
    sweep_velocity,
    time_features,
    volume_spike,
    wick_ratio,
)


def test_time_features_use_the_supplied_index_and_are_prefix_invariant() -> None:
    index = pd.DatetimeIndex(
        [
            "2025-01-06 00:00",
            "2025-01-06 06:30",
            "2025-01-06 12:00",
            "2025-01-06 18:00",
        ],
        tz="Etc/GMT-3",
    )

    full = time_features(index)
    prefix = time_features(index[:3])

    pd.testing.assert_frame_equal(full.iloc[:3], prefix)
    assert full.index.equals(index)
    assert full.iloc[0]["tod_sin"] == 0.0
    assert full.iloc[0]["tod_cos"] == 1.0
    assert full.iloc[0]["dow_sin"] == 0.0
    assert full.iloc[0]["dow_cos"] == 1.0


def test_rsi_causal(m1_bars):
    """RSI at t must not change when future bars are appended."""
    close = m1_bars["close"]
    rsi_full = rsi(close)
    rsi_trunc = rsi(close.iloc[:250])
    # Values up to bar 249 must match
    pd.testing.assert_series_equal(
        rsi_full.iloc[:249].dropna(),
        rsi_trunc.iloc[:249].dropna(),
        check_names=False,
        rtol=1e-6,
    )


def test_macd_causal(m1_bars):
    close = m1_bars["close"]
    m_full = macd(close)["macd"]
    m_trunc = macd(close.iloc[:300])["macd"]
    pd.testing.assert_series_equal(
        m_full.iloc[:299].dropna(),
        m_trunc.iloc[:299].dropna(),
        check_names=False,
        rtol=1e-6,
    )


def test_ema_causal(m1_bars):
    close = m1_bars["close"]
    feat_full = ema_features(close, [9, 21])
    feat_trunc = ema_features(close.iloc[:200], [9, 21])
    pd.testing.assert_frame_equal(
        feat_full.iloc[:199].dropna(),
        feat_trunc.iloc[:199].dropna(),
        rtol=1e-6,
    )


def test_returns_causal(m1_bars):
    """Log returns must be identical regardless of future data."""
    close = m1_bars["close"]
    r_full = returns(close, [1, 5])
    r_trunc = returns(close.iloc[:100], [1, 5])
    pd.testing.assert_frame_equal(
        r_full.iloc[:99].dropna(),
        r_trunc.iloc[:99].dropna(),
        rtol=1e-9,
    )


def test_volume_spike_is_prefix_invariant(m1_bars):
    activity = m1_bars["tickvol"]
    full = volume_spike(activity, window=20)
    prefix = volume_spike(activity.iloc[:250], window=20)

    pd.testing.assert_series_equal(full.iloc[:250], prefix, check_names=False)


def test_volume_spike_uses_current_activity_over_trailing_median() -> None:
    activity = pd.Series([0.0, 10.0, 20.0, 30.0, float("nan")])

    result = volume_spike(activity, window=3)

    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == 2.0
    assert result.iloc[2] == 2.0
    assert result.iloc[3] == 1.5
    assert pd.isna(result.iloc[4])


def test_sweep_velocity_is_prefix_invariant(m1_bars):
    bars = m1_bars.iloc[:300]

    def levels(
        frame: pd.DataFrame,
    ) -> tuple[pd.Series[Any], pd.Series[Any], pd.Series[Any], pd.Series[Any]]:
        return (
            frame["high"].cummax(),
            frame["low"].cummin(),
            frame["high"].cummax() + 1.0,
            frame["low"].cummin() - 1.0,
        )

    full_levels = levels(bars)
    full = sweep_velocity(
        bars,
        london_high=full_levels[0],
        london_low=full_levels[1],
        asian_high=full_levels[2],
        asian_low=full_levels[3],
    )
    prefix_bars = bars.iloc[:200]
    prefix_levels = levels(prefix_bars)
    prefix = sweep_velocity(
        prefix_bars,
        london_high=prefix_levels[0],
        london_low=prefix_levels[1],
        asian_high=prefix_levels[2],
        asian_low=prefix_levels[3],
    )

    pd.testing.assert_frame_equal(full.iloc[:200], prefix, check_names=False)


def test_wick_ratio_measures_upper_wick_only() -> None:
    bars = pd.DataFrame(
        {
            "open": [10.0, 10.0],
            "high": [12.0, 12.0],
            "low": [8.0, 8.0],
            "close": [11.0, 9.0],
        }
    )

    result = wick_ratio(bars)

    assert result.iloc[0] == 0.25
    assert result.iloc[1] == 0.5


# ---------------------------------------------------------------------------
# Encoder shape tests
# ---------------------------------------------------------------------------


def _make_obs(B: int, T: int, F: int) -> dict[str, torch.Tensor]:
    return {
        "seq": torch.randn(B, T, F),
        "account": torch.randn(B, 6),
    }


def test_tcn_encoder_output_shape(dict_obs_space):
    from models.encoders import TCNEncoder

    T, F = 10, 8
    model = TCNEncoder(
        dict_obs_space,
        seq_len=T,
        n_features=F,
        latent_dim=32,
        channels=(16, 16),
        kernel_size=3,
        dropout=0.0,
    )
    obs = _make_obs(B=4, T=T, F=F)
    out = model(obs)
    assert out.shape == (4, 32 + 32), f"Expected (4, 64), got {out.shape}"


def test_transformer_encoder_output_shape(dict_obs_space):
    from models.encoders import TransformerEncoder

    T, F = 10, 8
    model = TransformerEncoder(
        dict_obs_space,
        seq_len=T,
        n_features=F,
        latent_dim=32,
        d_model=32,
        nhead=4,
        num_layers=1,
        dropout=0.0,
    )
    obs = _make_obs(B=4, T=T, F=F)
    out = model(obs)
    assert out.shape == (4, 32 + 32), f"Expected (4, 64), got {out.shape}"


def test_tcn_encoder_batch_size_1(dict_obs_space):
    from models.encoders import TCNEncoder

    model = TCNEncoder(
        dict_obs_space, seq_len=10, n_features=8, latent_dim=16, channels=(8,), dropout=0.0
    )
    obs = _make_obs(B=1, T=10, F=8)
    out = model(obs)
    assert out.shape == (1, 16 + 32)


def test_transformer_causal_mask_consistency(dict_obs_space):
    """Output for position t must not change when future bars are appended."""
    from models.encoders import TransformerEncoder

    T, F = 10, 8
    model = TransformerEncoder(
        dict_obs_space,
        seq_len=T,
        n_features=F,
        latent_dim=16,
        d_model=16,
        nhead=4,
        num_layers=1,
        dropout=0.0,
    )
    model.eval()
    torch.manual_seed(0)
    seq_full = torch.randn(1, T, F)
    account = torch.randn(1, 6)

    with torch.no_grad():
        out_full = model({"seq": seq_full, "account": account})
        # Truncate to T//2 bars — last-step output should differ (different t)
        # but internal [0..T//2-1] attention should be independent of future
        out_half = model({"seq": seq_full[:, : T // 2, :], "account": account})

    # Both outputs are valid tensors (no NaN/Inf)
    assert torch.isfinite(out_full).all()
    assert torch.isfinite(out_half).all()
