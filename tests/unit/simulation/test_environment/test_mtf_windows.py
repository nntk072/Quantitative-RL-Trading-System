"""Closed higher-timeframe windows beside the M1 sequence."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch

from simulation.environment.env import TradingEnv
from simulation.environment.observations import (
    closed_window,
    run_starts,
    timeframe_starts,
)
from trading.strategies import PO3IFVGStrategy


def test_closed_m5_window_ends_on_the_candle_that_closed_at_1035() -> None:
    """A 10:37 decision sees 10:35, 10:30, 10:25. The 10:35-10:40 candle is absent."""
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    minute = index.hour * 60 + index.minute
    block = ((minute // 5) * 5).to_numpy(dtype=np.float64).reshape(-1, 1)
    decision = int(index.searchsorted(pd.Timestamp("2020-01-02 10:37")))
    window, mask = closed_window(block, run_starts(block), decision, 24)
    newest = window[mask > 0][-3:, 0]
    np.testing.assert_array_equal(newest, [10 * 60 + 25, 10 * 60 + 30, 10 * 60 + 35])
    assert not np.any(window == 10 * 60 + 40)


def test_closed_window_column_selection_matches_materialized_branch() -> None:
    """Column-selecting the tail window preserves values and padding exactly."""
    block = np.arange(120, dtype=np.float32).reshape(30, 4)
    block[8, 3] = np.nan
    starts = np.asarray([0, 3, 6, 9, 12, 15, 18, 21, 24, 27], dtype=np.int64)
    columns = np.asarray([1, 3], dtype=np.int64)

    for decision, length in ((0, 4), (5, 4), (18, 3), (29, 4)):
        expected, expected_mask = closed_window(block[:, columns], starts, decision, length)
        actual, actual_mask = closed_window(block, starts, decision, length, columns=columns)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(actual_mask, expected_mask)


def test_closed_window_maps_every_nonfinite_feature_to_zero() -> None:
    block = np.asarray([[1.0], [np.nan], [np.inf], [-np.inf], [2.0]], dtype=np.float32)

    window, mask = closed_window(block, np.arange(5), end=4, length=5)

    np.testing.assert_array_equal(window[:, 0], [1.0, 0.0, 0.0, 0.0, 2.0])
    np.testing.assert_array_equal(mask, np.ones(5, dtype=np.float32))


def test_closed_window_can_append_feature_validity_channels() -> None:
    block = np.asarray([[1.0], [np.nan], [np.inf], [-np.inf], [2.0]], dtype=np.float32)

    window, temporal_mask = closed_window(
        block, np.arange(5), end=4, length=7, include_validity=True
    )

    np.testing.assert_array_equal(window[-5:, 0], [1.0, 0.0, 0.0, 0.0, 2.0])
    np.testing.assert_array_equal(window[-5:, 1], [1.0, 0.0, 0.0, 0.0, 1.0])
    np.testing.assert_array_equal(window[:2], np.zeros((2, 2), dtype=np.float32))
    np.testing.assert_array_equal(temporal_mask, [0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0])


def test_environment_m1_observation_maps_infinite_features_to_zero() -> None:
    bars, features, decision = _day()
    features.loc[features.index[decision - 3], "sweep_high"] = np.inf
    features.loc[features.index[decision - 2], "sweep_high"] = -np.inf
    features.loc[features.index[decision - 1], "sweep_high"] = np.nan
    env = _env(bars, features, mtf=False)
    env.reset()
    env.step_idx = decision

    observation = env._get_observation()
    feature_column = env._obs_columns.index("sweep_high")

    assert np.isfinite(observation["seq"]).all()
    np.testing.assert_array_equal(observation["seq"][-3:, feature_column], [0.0, 0.0, 0.0])


def test_closed_window_without_available_candles_marks_every_row_invalid() -> None:
    block = np.zeros((3, 2), dtype=np.float32)

    window, mask = closed_window(
        block,
        np.zeros(0, dtype=np.int64),
        end=2,
        length=4,
    )

    np.testing.assert_array_equal(window, np.zeros((4, 2), dtype=np.float32))
    np.testing.assert_array_equal(mask, np.zeros(4, dtype=np.float32))


def test_timeframe_starts_preserve_equal_consecutive_candles() -> None:
    """Candle windows count source bars even when every feature value repeats."""
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    starts = timeframe_starts(index, "M3")
    decision = int(index.searchsorted(pd.Timestamp("2020-01-02 10:37")))
    repeated_features = np.zeros((len(index), 1), dtype=np.float32)
    window, mask = closed_window(repeated_features, starts, decision, 4)

    np.testing.assert_array_equal(mask, np.ones(4, dtype=np.float32))
    np.testing.assert_array_equal(window[:, 0], np.zeros(4, dtype=np.float32))
    assert int(np.count_nonzero(starts <= decision)) == 32


def test_timeframe_starts_include_scheduled_short_candle_close() -> None:
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    starts = timeframe_starts(
        index,
        "M5",
        {"2020-01-02": "10:37"},
        session_start="09:00",
    )

    assert pd.Timestamp("2020-01-02 10:37") in index[starts]


def _day() -> tuple[pd.DataFrame, pd.DataFrame, int]:
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    n = len(index)
    close = np.full(n, 100.0)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.ones(n),
            "session_id": np.zeros(n, dtype=int),
        },
        index=index,
    )
    minute = index.hour * 60 + index.minute
    features = pd.DataFrame(
        {
            "asian_high": np.full(n, 110.0),
            "asian_low": np.full(n, 90.0),
            "sweep_high": np.zeros(n),
            "sweep_low": np.ones(n),
            "po3_manipulation_low": np.full(n, 95.0),
            "po3_manipulation_high": np.full(n, 105.0),
            "po3_manipulation_end": np.full(n, 7.0),
            "po3_distribution": np.full(n, 3.0),
            "po3_distribution_direction": np.ones(n),
            "ifvg_bull_low": np.full(n, 98.0),
            "ifvg_bull_high": np.full(n, 99.0),
            "price_in_ifvg_bull": np.ones(n),
            "ifvg_retest_bull": np.ones(n),
            "ifvg_bear_low": np.zeros(n),
            "ifvg_bear_high": np.zeros(n),
            "ifvg_bull_active": np.ones(n),
            "ifvg_bear_active": np.zeros(n),
            "last_swing_high": np.full(n, 120.0),
            "last_swing_low": np.full(n, 80.0),
            "london_high": np.full(n, 112.0),
            "london_low": np.full(n, 88.0),
            "htf_day_bias": np.ones(n),
            "context_trade_direction": np.ones(n),
            "manip_reverses_htf": np.zeros(n),
            "atr_5": np.ones(n),
            "prev_day_high": np.full(n, 150.0),
            "prev_day_low": np.full(n, 50.0),
            "M5_bias": ((minute // 5) * 5).to_numpy(dtype=float),
            "M15_bias": ((minute // 15) * 15).to_numpy(dtype=float),
            "H1_bias": ((minute // 60) * 60).to_numpy(dtype=float),
        },
        index=index,
    )
    decision = int(index.searchsorted(pd.Timestamp("2020-01-02 10:37")))
    return bars, features, decision


def _env(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    *,
    mtf: bool,
    vae: torch.nn.Module | None = None,
    pre_ny_data: pd.DataFrame | None = None,
    feature_validity_channels: bool = False,
) -> TradingEnv:
    return TradingEnv(
        bars,
        features,
        strategy_actions=True,
        strategy=PO3IFVGStrategy(enforce_gate=False),
        sl_buffer_pts=0.0,
        obs_window=10,
        initial_balance=100_000.0,
        risk_frac_range=(0.01, 0.01),
        min_sl_points=0.0,
        min_sl_atr_mult=0.0,
        allow_agent_sl_mode=False,
        mtf=mtf,
        mtf_windows={"m5": 24, "m15": 16, "h1": 12},
        use_vae=vae is not None,
        vae=vae,
        pre_ny_data=pre_ny_data,
        feature_validity_channels=feature_validity_channels,
    )


def test_opt_in_m1_validity_distinguishes_missing_from_valid_zero() -> None:
    bars, features, decision = _day()
    features.loc[features.index[decision - 3], "sweep_high"] = np.nan
    features.loc[features.index[decision - 2], "sweep_high"] = 0.0
    features.loc[features.index[decision - 1], "sweep_high"] = np.inf
    env = _env(bars, features, mtf=False, feature_validity_channels=True)
    env.reset()
    env.step_idx = decision

    observation = env._get_observation()
    column = env._obs_columns.index("sweep_high")
    width = len(env._obs_columns)

    np.testing.assert_array_equal(observation["seq"][-3:, column], [0.0, 0.0, 0.0])
    np.testing.assert_array_equal(observation["seq"][-3:, width + column], [0.0, 1.0, 0.0])
    np.testing.assert_array_equal(observation["seq_mask"][-3:], [1.0, 1.0, 1.0])
    assert observation["seq"].shape[1] == width * 2
    assert env.observation_space.contains(observation)


def test_opt_in_mtf_validity_masks_missing_columns_and_padding() -> None:
    bars, features, decision = _day()
    env = _env(bars, features.drop(columns=["H1_bias"]), mtf=True, feature_validity_channels=True)
    env.reset()
    env.step_idx = decision

    observation = env._get_observation()

    assert observation["seq_h1"].shape == (12, 2)
    np.testing.assert_array_equal(observation["seq_h1"], np.zeros((12, 2), dtype=np.float32))
    np.testing.assert_array_equal(observation["mask_h1"], np.zeros(12, dtype=np.float32))
    assert observation["seq_m5"].shape[1] == 2
    assert env.observation_space.contains(observation)


class _FiniteInputVAE(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = SimpleNamespace(seq_len=4, n_features=1, latent_dim=2)
        self.device_anchor = torch.nn.Parameter(torch.zeros(()))
        self.received: torch.Tensor | None = None

    def encode(self, values: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        self.received = values.detach().clone()
        latent = values.new_zeros((values.shape[0], self.encoder.latent_dim))
        return latent, latent


def test_vae_context_maps_nonfinite_input_features_to_zero() -> None:
    bars, features, _decision = _day()
    vae = _FiniteInputVAE()
    pre_ny = pd.DataFrame([[np.nan, np.inf, -np.inf, 1.0]])
    env = _env(bars, features, mtf=False, vae=vae, pre_ny_data=pre_ny)
    env.reset()

    observation = env._get_observation()

    assert vae.received is not None
    np.testing.assert_array_equal(vae.received[0, :, 0].cpu().numpy(), [0.0, 0.0, 0.0, 1.0])
    assert np.isfinite(observation["vae_z"]).all()


def test_column_ownership_and_closed_bars() -> None:
    bars, features, decision = _day()
    mtf = _env(bars, features, mtf=True)
    single = _env(bars, features, mtf=False)
    mtf.reset()
    single.reset()
    mtf.step_idx = decision
    single.step_idx = decision
    obs = mtf._get_observation()
    base = single._get_observation()

    assert set(base) == {"seq", "seq_mask", "account"}
    assert obs["seq_m5"].shape == (24, 1)
    assert obs["seq_m15"].shape == (16, 1)
    assert obs["seq_h1"].shape == (12, 1)
    assert obs["seq_m3"].shape == (20, 1)
    assert obs["seq_m10"].shape == (12, 1)
    assert obs["seq_m30"].shape == (8, 1)
    assert obs["seq_h4"].shape == (6, 1)
    assert obs["seq_d1"].shape == (5, 1)
    assert obs["seq"].shape[1] == base["seq"].shape[1] - 3
    np.testing.assert_array_equal(obs["seq"], base["seq"][:, mtf._m1_idx])
    assert np.any(obs["seq"] == 3.0)
    assert np.any(obs["seq"] == 7.0)
    assert not np.any(obs["seq"] >= 500.0)
    np.testing.assert_array_equal(obs["seq_m5"][obs["mask_m5"] > 0][-3:, 0], [625, 630, 635])
    assert not np.any(obs["seq_m5"] == 640)
    np.testing.assert_array_equal(obs["seq_m15"][obs["mask_m15"] > 0][-1, 0], [630])
    np.testing.assert_array_equal(obs["seq_h1"][obs["mask_h1"] > 0][-1, 0], [600])
    assert not np.any(obs["seq_m5"] == 3.0)
    assert np.any(base["seq"] == 635)
    np.testing.assert_array_equal(obs["account"], base["account"])
    assert mtf.observation_space.contains(obs)
    assert mtf.action_space.shape == (5,)
    directed = TradingEnv(
        bars,
        features,
        strategy_actions=True,
        strategy=PO3IFVGStrategy(enforce_gate=False),
        obs_window=10,
        agent_direction_control=True,
        allow_agent_sl_mode=False,
        mtf=True,
    )
    assert directed.action_space.shape == (6,)
    bare = features.drop(columns=["H1_bias"])
    empty = _env(bars, bare, mtf=True)
    empty.reset()
    empty.step_idx = decision
    missing = empty._get_observation()
    assert missing["seq_h1"].shape == (12, 1)
    assert np.all(missing["mask_h1"] == 0.0)
    assert np.all(missing["seq_h1"] == 0.0)


def test_same_action_resolves_the_same_stop_and_target() -> None:
    bars, features, _decision = _day()
    action = np.array([0.9, 0.0, 0.5, 0.0, -1.0], dtype=np.float32)
    opened: dict[str, tuple[float, float]] = {}
    for name, mtf in (("tcn", False), ("mtf", True)):
        env = _env(bars, features, mtf=mtf)
        env.reset()
        for _ in range(30):
            env.step(action)
            if env.position is not None:
                stop = env.position.sl_price
                target = env.position.tp_price
                assert stop is not None and target is not None
                opened[name] = (float(stop), float(target))
                break
    assert opened["tcn"] == opened["mtf"]
    assert opened["tcn"][0] != opened["tcn"][1]
