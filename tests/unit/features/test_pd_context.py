"""Unit tests for session-conditional PD context (masking + no lookahead)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
from omegaconf import DictConfig, OmegaConf

from features import OBS_RAW_PRICE_COLUMNS, build_features
from features.context.liquidity import detect_bos, detect_mss
from features.context.premium_discount import (
    PD_CONTEXT_FEATURE_COLUMNS,
    build_pd_context_features,
    build_trader_context_features,
)
from features.technical.structure import structure_levels
from market_data.transforms.sessions import add_session_labels
from simulation.environment.observations import prepare_observation_feature_channels


def _index_dates(idx: pd.Index) -> np.ndarray[Any, Any]:
    """Calendar dates from a DatetimeIndex (mypy-safe)."""
    return np.asarray(pd.DatetimeIndex(idx).date)


def _two_day_bars() -> pd.DataFrame:
    """Two broker days covering Asia → London → NY with known extremes."""
    # Day 1: 2025-01-06 (Mon), Day 2: 2025-01-07
    chunks: list[pd.DataFrame] = []
    rng = np.random.default_rng(7)
    for day, asia_base, lon_base, ny_base in (
        ("2025-01-06", 100.0, 110.0, 105.0),
        ("2025-01-07", 120.0, 130.0, 125.0),
    ):
        for start, end, base in (
            (f"{day} 01:05", f"{day} 08:59", asia_base),
            (f"{day} 09:00", f"{day} 16:29", lon_base),
            (f"{day} 16:30", f"{day} 22:59", ny_base),
        ):
            idx = pd.date_range(start, end, freq="1min", tz="Etc/GMT-3")
            n = len(idx)
            noise = rng.uniform(-0.5, 0.5, n)
            close = base + noise
            # Plant a unique extreme mid-session so completed H/L are identifiable.
            high = close + 0.2
            low = close - 0.2
            mid = n // 2
            high[mid] = base + 5.0
            low[mid + 1 if mid + 1 < n else mid] = base - 5.0
            chunks.append(
                pd.DataFrame(
                    {
                        "open": close,
                        "high": high,
                        "low": low,
                        "close": close,
                        "volume": np.full(n, 100.0),
                        "tickvol": np.full(n, 50),
                    },
                    index=idx,
                )
            )
    out = pd.concat(chunks).sort_index()
    out.index.name = "datetime"
    return out


@pytest.fixture
def bars() -> pd.DataFrame:
    return _two_day_bars()


class TestPdContextRouting:
    def test_asia_masks_london_and_asia_ctx(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        asia = add_session_labels(bars)["session"] == "asia"
        assert asia.any()
        assert (ctx.loc[asia, "ctx_asia_active"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_london_active"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_asia_high"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_london_high"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_asia_high_dist_atr"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_london_high_dist_atr"] == 0.0).all()
        # Prev-day summaries remain available (NaN only on first calendar day).
        day2_asia = asia & (_index_dates(bars.index) == pd.Timestamp("2025-01-07").date())
        assert day2_asia.any()
        assert ctx.loc[day2_asia, "ctx_prev_day_high"].notna().all()

    def test_london_has_asia_not_completed_self_as_running(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        london = add_session_labels(bars)["session"] == "london"
        assert london.any()
        assert (ctx.loc[london, "ctx_asia_active"] == 1.0).all()
        assert (ctx.loc[london, "ctx_london_active"] == 1.0).all()
        # Completed Asia for day 1 should equal planted asia extreme 105.
        d1_lon = london & (_index_dates(bars.index) == pd.Timestamp("2025-01-06").date())
        assert np.allclose(ctx.loc[d1_lon, "ctx_asia_high"].to_numpy(), 105.0)
        # London high is live/running — first London bar cannot yet see the mid-session plant.
        first_lon = ctx.loc[d1_lon].iloc[0]
        assert first_lon["ctx_london_high"] < 115.0
        last_lon = ctx.loc[d1_lon].iloc[-1]
        assert np.isclose(last_lon["ctx_london_high"], 115.0)

    def test_ny_has_completed_asia_and_london(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        ny = add_session_labels(bars)["session"] == "ny"
        d1_ny = ny & (_index_dates(bars.index) == pd.Timestamp("2025-01-06").date())
        assert d1_ny.any()
        assert (ctx.loc[d1_ny, "ctx_asia_active"] == 1.0).all()
        assert (ctx.loc[d1_ny, "ctx_london_active"] == 1.0).all()
        assert np.allclose(ctx.loc[d1_ny, "ctx_asia_high"].to_numpy(), 105.0)
        assert np.allclose(ctx.loc[d1_ny, "ctx_london_high"].to_numpy(), 115.0)

    def test_no_lookahead_across_session_boundary(self, bars: pd.DataFrame) -> None:
        """First London bar must not see London's eventual session high."""
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        d1 = _index_dates(bars.index) == pd.Timestamp("2025-01-06").date()
        london = (add_session_labels(bars)["session"] == "london") & d1
        ny = (add_session_labels(bars)["session"] == "ny") & d1
        first_lon_hi = float(ctx.loc[london, "ctx_london_high"].iloc[0])
        final_lon_hi = float(ctx.loc[ny, "ctx_london_high"].iloc[0])
        assert first_lon_hi < final_lon_hi
        # Asia bars must not see same-day London at all.
        asia = (add_session_labels(bars)["session"] == "asia") & d1
        assert (ctx.loc[asia, "ctx_london_high"] == 0.0).all()

    def test_fixed_width_columns(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        for col in PD_CONTEXT_FEATURE_COLUMNS:
            assert col in ctx.columns

    def test_day_bias_availability_distinguishes_unknown_from_neutral(
        self, bars: pd.DataFrame
    ) -> None:
        atr = pd.Series(1.0, index=bars.index)
        initial = build_pd_context_features(bars, atr)
        unavailable = initial.index[initial["htf_day_bias_available"] == 0.0][0]
        assert initial.loc[unavailable, "htf_day_bias"] == 0.0
        assert not np.isfinite(initial.loc[unavailable, "ctx_pd_mid_dist_atr"])

        available = initial.index[initial["htf_day_bias_available"] == 1.0][0]
        assert initial.loc[available, "ctx_asia_active"] == 1.0
        assert initial.loc[available, "ctx_london_active"] == 1.0
        midpoint = (
            max(
                initial.loc[available, "ctx_asia_high"],
                initial.loc[available, "ctx_london_high"],
            )
            + min(
                initial.loc[available, "ctx_asia_low"],
                initial.loc[available, "ctx_london_low"],
            )
        ) / 2.0
        neutral_bars = bars.copy()
        neutral_bars.loc[available, "close"] = midpoint
        neutral = build_pd_context_features(neutral_bars, atr)

        assert np.isclose(neutral.loc[available, "ctx_pd_mid_dist_atr"], 0.0)
        assert neutral.loc[available, "htf_day_bias"] == 0.0
        assert neutral.loc[available, "htf_day_bias_available"] == 1.0

    def test_unavailable_active_distances_remain_nonfinite(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        london = add_session_labels(bars)["session"] == "london"
        missing_atr_bar = bars.index[london][0]
        atr.loc[missing_atr_bar] = np.nan

        ctx = build_pd_context_features(bars, atr)

        assert np.isnan(ctx.loc[missing_atr_bar, "ctx_asia_high_dist_atr"])
        assert np.isnan(ctx.loc[missing_atr_bar, "ctx_london_high_dist_atr"])
        assert np.isnan(ctx.loc[missing_atr_bar, "ctx_pd_mid_dist_atr"])

        columns = [
            "ctx_asia_high_dist_atr",
            "ctx_london_high_dist_atr",
            "ctx_pd_mid_dist_atr",
        ]
        channels = prepare_observation_feature_channels(
            ctx.loc[[missing_atr_bar], columns].to_numpy(dtype=np.float32),
            include_validity=True,
        )
        np.testing.assert_array_equal(channels[0, :3], np.zeros(3, dtype=np.float32))
        np.testing.assert_array_equal(channels[0, 3:], np.zeros(3, dtype=np.float32))

    def test_missing_active_session_range_is_not_zero_filled(self, bars: pd.DataFrame) -> None:
        sessions = add_session_labels(bars)["session"]
        day_two = _index_dates(bars.index) == pd.Timestamp("2025-01-07").date()
        incomplete = bars.loc[~(day_two & sessions.eq("asia"))]
        atr = pd.Series(1.0, index=incomplete.index)

        ctx = build_pd_context_features(incomplete, atr)
        day_two_london = (
            _index_dates(incomplete.index) == pd.Timestamp("2025-01-07").date()
        ) & add_session_labels(incomplete)["session"].eq("london").to_numpy()

        assert day_two_london.any()
        assert (ctx.loc[day_two_london, "ctx_asia_active"] == 1.0).all()
        assert ctx.loc[day_two_london, "ctx_asia_high_dist_atr"].isna().all()
        assert ctx.loc[day_two_london, "ctx_asia_low_dist_atr"].isna().all()


class TestMssCausal:
    def test_mss_flips_after_opposite_bos(self) -> None:
        idx = pd.date_range("2025-01-06 16:30", periods=40, freq="1min", tz="Etc/GMT-3")
        close = np.concatenate(
            [
                np.linspace(100, 90, 10),  # down
                np.linspace(90, 95, 10),  # bounce
                np.linspace(95, 85, 10),  # continue down → bos_down likely
                np.linspace(85, 100, 10),  # reverse up → bos_up / mss_up
            ]
        )
        bars = pd.DataFrame(
            {
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
            },
            index=idx,
        )
        struct = structure_levels(bars, swing_period=2)[["last_swing_high", "last_swing_low"]]
        bos = detect_bos(bars, struct)
        mss = detect_mss(bars, struct, bos)
        # If any MSS fires, it must coincide with a BOS on the same bar.
        mss_up_idx = mss.index[mss["mss_up"] == 1]
        for t in mss_up_idx:
            assert bos.loc[t, "bos_up"] == 1
        mss_dn_idx = mss.index[mss["mss_down"] == 1]
        for t in mss_dn_idx:
            assert bos.loc[t, "bos_down"] == 1

    def test_mss_marks_only_exact_changes_in_bos_direction(self) -> None:
        idx = pd.date_range("2025-01-06 16:30", periods=7, freq="1min", tz="Etc/GMT-3")
        bars = pd.DataFrame({"close": np.full(len(idx), 100.0)}, index=idx)
        structure = pd.DataFrame(index=idx)
        bos = pd.DataFrame(
            {
                "bos_up": [0, 0, 0, 1, 0, 0, 0],
                "bos_down": [0, 1, 1, 0, 0, 0, 1],
                "bos_up_level": [np.nan, np.nan, np.nan, 101.0, np.nan, np.nan, np.nan],
                "bos_down_level": [np.nan, 99.0, 98.0, np.nan, np.nan, np.nan, 97.0],
            },
            index=idx,
        )

        result = detect_mss(bars, structure, bos)

        assert result["mss_up"].tolist() == [0, 0, 0, 1, 0, 0, 0]
        assert result["mss_down"].tolist() == [0, 0, 0, 0, 0, 0, 1]
        assert np.isnan(result["mss_up_level"].iloc[2])
        assert result["mss_up_level"].iloc[3] == pytest.approx(101.0)
        assert result["mss_down_level"].iloc[6] == pytest.approx(97.0)
        pd.testing.assert_frame_equal(
            result.iloc[:4],
            detect_mss(bars.iloc[:4], structure.iloc[:4], bos.iloc[:4]),
        )


def _pd_cfg(**overrides: Any) -> DictConfig:
    base: dict[str, Any] = {
        "features": {
            "ema_periods": [9, 21],
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "atr_period": 14,
            "adx_period": 14,
            "bb_period": 20,
            "bb_std": 2.0,
            "stoch_k": 14,
            "stoch_d": 3,
            "vwap_session": False,
            "return_horizons": [1, 5],
            "realized_vol_period": 20,
            "smt_swing_period": 5,
            "smt_corr_window": 20,
            "zscore_window": 50,
            "htf_timeframes": ["M5", "M15"],
            "include_po3": False,
            "include_fvg_ifvg": False,
            "include_po3_full": False,
            "include_strategy_state": False,
            "include_session_ohlc": False,
            "include_pd_context": True,
            "structure": {"enabled": True, "timeframes": ["M5", "M15"]},
        },
        "session": {"timezone": "Etc/GMT-3"},
    }
    base["features"].update(overrides)
    cfg = OmegaConf.create(base)
    assert isinstance(cfg, DictConfig)
    return cfg


class TestBuildFeaturesPdContext:
    def test_pd_columns_and_htf_pd_present(self, bars: pd.DataFrame) -> None:
        feat = build_features(bars, cfg=_pd_cfg())
        for col in ("ctx_asia_active", "bos_up", "mss_up", "active_session_ny"):
            assert col in feat.columns
        assert any(c.startswith("M15_pd_") for c in map(str, feat.columns))
        assert any(c.startswith("M5_bos_") or c == "M5_bos_up" for c in map(str, feat.columns))

    def test_ny_nonzero_asia_zero_mask_in_pipeline(self, bars: pd.DataFrame) -> None:
        feat = build_features(bars, cfg=_pd_cfg())
        labeled = add_session_labels(bars)
        ny = labeled["session"] == "ny"
        asia = labeled["session"] == "asia"
        # Align masks to feat index (dropna may trim leading rows).
        ny = ny.reindex(feat.index).fillna(False).astype(bool)
        asia = asia.reindex(feat.index).fillna(False).astype(bool)
        assert (feat.loc[asia, "ctx_london_high_dist_atr"] == 0.0).all()
        # NY bars on day 2 should have non-zero asia active + filled levels.
        d2_ny = ny & (_index_dates(feat.index) == pd.Timestamp("2025-01-07").date())
        assert d2_ny.any()
        assert (feat.loc[d2_ny, "ctx_asia_active"] == 1.0).all()
        assert (feat.loc[d2_ny, "ctx_asia_high"] != 0.0).any()

    def test_obs_raw_stems_include_ctx_levels(self) -> None:
        assert "ctx_asia_high" in OBS_RAW_PRICE_COLUMNS
        assert "mss_up_level" in OBS_RAW_PRICE_COLUMNS
        assert "asian_high" in OBS_RAW_PRICE_COLUMNS


class TestTraderContextComposition:
    def test_distribution_precedes_reversal_then_falls_back_to_htf_bias(self) -> None:
        idx = pd.date_range("2025-01-06 16:30", periods=3, freq="1min", tz="Etc/GMT-3")
        feat = pd.DataFrame(
            {
                "htf_day_bias": [2.0, -2.0, 0.0],
                "po3_manipulation_active": [1.0, 1.0, 0.0],
                "po3_manipulation_direction": [-1.0, 1.0, 0.0],
                "po3_distribution": [0.0, 1.0, 0.0],
                "po3_distribution_direction": [0.0, 1.0, 0.0],
                "po3_manipulation_end": [0.0, 0.0, 1.0],
            },
            index=idx,
        )

        result = build_trader_context_features(feat)

        assert result.index.equals(idx)
        assert result["htf_day_bias"].tolist() == [1.0, -1.0, 0.0]
        assert result["manip_reverses_htf"].tolist() == [1.0, 1.0, 0.0]
        assert result["context_trade_direction"].tolist() == [-1.0, 1.0, 0.0]

    def test_context_flags_supply_bias_when_htf_column_is_absent(self) -> None:
        idx = pd.date_range("2025-01-06 16:30", periods=3, freq="1min", tz="Etc/GMT-3")
        feat = pd.DataFrame(
            {
                "ctx_in_discount": [1.0, 0.0, 0.0],
                "ctx_in_premium": [0.0, 1.0, 0.0],
            },
            index=idx,
        )

        result = build_trader_context_features(feat)

        assert result["htf_day_bias"].tolist() == [1.0, -1.0, 0.0]
        assert result["manip_reverses_htf"].tolist() == [0.0, 0.0, 0.0]
        assert result["context_trade_direction"].tolist() == [1.0, -1.0, 0.0]


class TestConfigYaml:
    def test_po3_ifvg_enables_pd_context(self) -> None:
        from configuration import load_config

        cfg = load_config(config_path="config/2_po3_ifvg.yaml")
        assert cfg.features.include_pd_context is True
        assert cfg.features.structure.enabled is True

    def test_features_pd_context_yaml(self) -> None:
        from configuration import load_config

        cfg = load_config(config_path="config/features/pd_context.yaml")
        assert cfg.features.include_pd_context is True
