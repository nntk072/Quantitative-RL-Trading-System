"""Value-level causal checks of the registry's families on the tracked example bars.

Every check runs the real build path (build_features / build_indicators / align_timeframes) on
data/examples only. Batch-vs-streaming and incremental-vs-full checks are not applicable: the
repository has no streaming feature state (no streaming, incremental or partial_fit path in
features/, market_data/ or live/).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from omegaconf import DictConfig

from configuration.configuration_loader import load_config
from features import build_features
from features.registry import PRIMARY, registry_nodes
from features.technical import indicators as ind
from market_data.arrow_schemas import mt5_export_to_bars
from market_data.splits.walkforward import purged_walk_forward
from market_data.transforms.align import align_timeframes, timeframe_close_times
from market_data.transforms.resample import TF, resample

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
HTF = ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
PRICE = ["open", "high", "low", "close"]


def load_example_bars() -> pd.DataFrame:
    frame = pd.read_csv(EXAMPLE, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert problems == []
    bars: pd.DataFrame = table.select(
        ["event_time", "open", "high", "low", "close", "volume"]
    ).to_pandas()
    bars.index = pd.DatetimeIndex(bars.pop("event_time"))
    return bars


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    return load_example_bars()


@pytest.fixture(scope="module")
def cfg() -> DictConfig:
    return load_config()


@pytest.fixture(scope="module")
def base(bars: pd.DataFrame, cfg: DictConfig) -> pd.DataFrame:
    return build_features(bars, cfg=cfg)


def assert_same_values(actual: pd.DataFrame, expected: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(actual, expected, check_exact=True)


def leading_nulls(series: pd.Series) -> int:
    values = series.isna().to_numpy()
    return int(np.argmin(values)) if not values.all() else len(values)


def test_future_removal_leaves_earlier_values_identical(bars, cfg, base) -> None:
    for cut in (300, 1000, 2000):
        prefix = build_features(bars.iloc[:cut], cfg=cfg)
        assert len(prefix) == cut
        assert_same_values(prefix, base.loc[prefix.index])


def test_future_append_leaves_earlier_values_identical(bars, cfg, base) -> None:
    cut = 1200
    future = bars.iloc[cut:].copy()
    future.index = future.index + pd.Timedelta(days=7)
    future[PRICE] = future[PRICE] * 1.1
    extended = build_features(pd.concat([bars.iloc[:cut], future]), cfg=cfg)
    assert_same_values(extended.loc[bars.index[:cut]], base.loc[bars.index[:cut]])


def test_held_out_perturbation_leaves_pre_cutoff_values_identical(bars, cfg) -> None:
    cut = 1500
    train_mask = pd.Series(np.arange(len(bars)) < cut, index=bars.index)
    perturbed = bars.copy()
    perturbed.iloc[cut:, perturbed.columns.get_indexer(PRICE)] = (
        perturbed.iloc[cut:][PRICE].to_numpy() * 1.5
    )
    original = build_features(bars, cfg=cfg, train_mask=train_mask)
    changed = build_features(perturbed, cfg=cfg, train_mask=train_mask)
    pre = bars.index[:cut]
    assert_same_values(changed.loc[pre], original.loc[pre])
    assert not changed.loc[bars.index[cut:]].equals(original.loc[bars.index[cut:]])


def test_higher_timeframe_value_is_visible_only_after_its_bar_closes(bars, cfg) -> None:
    h1 = resample(bars, "H1")
    block = ind.build_indicators(h1, cfg.features)
    closes = timeframe_close_times(h1, "H1")
    aligned = align_timeframes(bars, {"H1": block}, availability_times={"H1": closes})
    closes_ns = np.array([ts.value for ts in closes], dtype=np.int64)
    for t, row in aligned[["H1_ema_9", "H1_rsi"]].iterrows():
        position = int(np.searchsorted(closes_ns, pd.Timestamp(str(t)).value, side="right")) - 1
        if position < 0:
            assert row.isna().all()
            continue
        expected = block.iloc[position][["ema_9", "rsi"]].to_numpy(dtype=float)
        np.testing.assert_array_equal(row.to_numpy(dtype=float), expected)


def test_changing_bars_inside_an_open_hour_does_not_reach_earlier_htf_values(bars, cfg) -> None:
    h1 = resample(bars, "H1")
    counts = bars.resample("1h", label="left", closed="left").size()
    label = next(
        t
        for t in h1.index[1:]
        if counts.get(t, 0) == 60 and counts.get(t - pd.Timedelta(hours=1), 0) == 60
    )
    inside = (bars.index >= label) & (bars.index < label + pd.Timedelta(hours=1))
    perturbed = bars.copy()
    perturbed.loc[inside, PRICE] = perturbed.loc[inside, PRICE] * 1.2

    def htf(frame: pd.DataFrame) -> pd.DataFrame:
        bar_frame = resample(frame, "H1")
        block = ind.build_indicators(bar_frame, cfg.features)
        closes = timeframe_close_times(bar_frame, "H1")
        return align_timeframes(frame, {"H1": block}, availability_times={"H1": closes})

    original, changed = htf(bars), htf(perturbed)
    before_close = bars.index < label + pd.Timedelta(hours=1)
    columns = [c for c in original.columns if c.startswith("H1_")]
    pd.testing.assert_frame_equal(
        changed.loc[before_close, columns], original.loc[before_close, columns], check_exact=True
    )
    after = ~before_close
    assert not changed.loc[after, columns].equals(original.loc[after, columns])


def test_warmup_is_exactly_the_declared_leading_null_run(bars, cfg, base) -> None:
    for node in registry_nodes(cfg.features):
        if node.timeframe != PRIMARY or not node.outputs or node.node_id == "M1.prev_day_range":
            continue
        leads = [leading_nulls(base[column.name]) for column in node.outputs]
        assert max(leads) == node.warmup_bars, node.node_id
        for column in node.outputs:
            assert base[column.name].iloc[node.warmup_bars :].notna().all(), column.name


def test_higher_timeframe_warmup_bounds_the_leading_nulls_of_their_own_bars(bars, cfg) -> None:
    for node in registry_nodes(cfg.features):
        if node.timeframe not in HTF or not node.outputs:
            continue
        block = ind.build_indicators(resample(bars, cast(TF, node.timeframe)), cfg.features)
        for column in node.outputs:
            name = column.name[len(node.timeframe) + 1 :]
            assert leading_nulls(block[name]) <= node.warmup_bars, column.name


def test_missing_bar_does_not_change_earlier_values(bars, cfg, base) -> None:
    gap = 1500
    dropped = build_features(bars.drop(bars.index[gap]), cfg=cfg)
    earlier = bars.index[:gap]
    assert_same_values(dropped.loc[earlier], base.loc[earlier])


def test_missing_close_is_not_backfilled_into_earlier_indicator_values(bars) -> None:
    holed = bars.copy()
    holed.iloc[1500, holed.columns.get_loc("close")] = np.nan
    features = load_config().features
    original = ind.build_indicators(bars, features)
    with_gap = ind.build_indicators(holed, features)
    pd.testing.assert_frame_equal(with_gap.iloc[:1500], original.iloc[:1500], check_exact=True)


def test_purge_and_embargo_guarantees_of_the_existing_splitter(bars) -> None:
    purge, embargo, horizon = 60, 20, 5
    splits = list(
        purged_walk_forward(
            len(bars),
            n_splits=4,
            test_size=0.2,
            purge_bars=purge,
            embargo_bars=embargo,
            label_horizon=horizon,
        )
    )
    assert len(splits) == 4
    seen: list[Any] = []
    for split in splits:
        gap = int(split.test_idx.min()) - int(split.train_idx.max()) - 1
        assert gap >= embargo + purge + horizon
        assert np.all(np.diff(split.test_idx) == 1)
        seen.append(split.test_idx)
    combined = np.concatenate(seen)
    assert len(np.unique(combined)) == len(combined)


@pytest.mark.xfail(
    strict=True,
    reason="known defect: detect_session_levels reindexes date-keyed prior-day highs/lows "
    "against a DatetimeIndex, so prev_day_high and prev_day_low are always null",
)
def test_prev_day_high_and_low_are_populated(base: pd.DataFrame) -> None:
    assert base["prev_day_high"].notna().any()
    assert base["prev_day_low"].notna().any()
