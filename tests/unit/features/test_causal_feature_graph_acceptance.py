"""CAUSAL-FEATURE-GRAPH acceptance: cache identity covers every feature source, and every
declared higher timeframe is causal (completed bars only).

Uses the tracked example bars and a deterministic synthetic M1 series. No broker data is fabricated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from omegaconf import DictConfig

from configuration.configuration_loader import load_config
from features import feature_cache_content_hash, registry
from features.registry import registry_nodes
from features.technical import indicators as ind
from market_data.transforms.align import align_timeframes, timeframe_close_times
from market_data.transforms.resample import resample

REPO = Path(registry.__file__).resolve().parents[1]
HTF = ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
PRICE = ["open", "high", "low", "close"]


@pytest.fixture(scope="module")
def cfg() -> DictConfig:
    return load_config()


def synthetic_m1(days: int = 6, seed: int = 7) -> pd.DataFrame:
    """Contiguous UTC M1 bars with a seeded random walk. No gaps, so every HTF bar is complete."""
    rng = np.random.default_rng(seed)
    n = days * 1440
    index = pd.date_range("2025-01-06 00:00", periods=n, freq="min", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0.0, 0.1, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    spread = np.abs(rng.normal(0.0, 0.05, n))
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + spread,
            "low": np.minimum(open_, close) - spread,
            "close": close,
            "volume": rng.integers(1, 6, n).astype(float),
        },
        index=index,
    )


def align_one(bars: pd.DataFrame, tf: str, cfg: DictConfig) -> pd.DataFrame:
    """Align one higher timeframe with the same calls the feature build uses."""
    bar_frame = resample(bars, tf)  # type: ignore[arg-type]
    block = ind.build_indicators(bar_frame, cfg.features)
    closes = timeframe_close_times(bar_frame, tf)
    return align_timeframes(bars, {tf: block}, availability_times={tf: closes})


# ---- cache identity -------------------------------------------------------------------------


def test_code_identity_covers_feature_modules_outside_the_declared_families() -> None:
    # Undeclared blocks (order blocks, PO3/FVG, pipeline stages) are used by build_features and
    # must change the cache key when their source changes.
    covered = set(registry.source_files())
    for rel in (
        "features/context/order_blocks.py",
        "features/po3/fvg.py",
        "features/pipeline/feature_matrix_builder.py",
        "market_data/transforms/align.py",
    ):
        assert REPO / rel in covered, rel


def test_code_identity_changes_when_an_undeclared_source_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "features"
    root.mkdir()
    module = root / "context_block.py"
    module.write_text("def block():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr(registry, "SOURCE_ROOTS", (root,))
    before = registry.code_identity()
    assert registry.code_identity() == before
    module.write_text("def block():\n    return 2\n", encoding="utf-8")
    assert registry.code_identity() != before


def test_cache_key_changes_when_an_undeclared_source_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cfg: DictConfig
) -> None:
    bars = synthetic_m1(days=1)
    root = tmp_path / "features"
    root.mkdir()
    module = root / "po3_block.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(registry, "SOURCE_ROOTS", (root,))
    before = feature_cache_content_hash(cfg, bars)
    module.write_text("VALUE = 2\n", encoding="utf-8")
    assert feature_cache_content_hash(cfg, bars) != before


# ---- causal availability of every declared higher timeframe ---------------------------------


@pytest.mark.parametrize("tf", HTF)
def test_htf_value_equals_the_last_completed_bar_at_every_minute(tf: str, cfg: DictConfig) -> None:
    bars = synthetic_m1()
    bar_frame = resample(bars, tf)  # type: ignore[arg-type]
    block = ind.build_indicators(bar_frame, cfg.features)
    closes = timeframe_close_times(bar_frame, tf)
    aligned = align_timeframes(bars, {tf: block}, availability_times={tf: closes})
    closes_ns = np.array([ts.value for ts in closes], dtype=np.int64)
    row_ns = np.array([ts.value for ts in aligned.index], dtype=np.int64)
    positions = np.searchsorted(closes_ns, row_ns, side="right") - 1
    for column in block.columns:
        values = block[column].to_numpy(dtype=float)
        expected = np.where(positions >= 0, values[np.clip(positions, 0, None)], np.nan)
        np.testing.assert_array_equal(
            aligned[f"{tf}_{column}"].to_numpy(dtype=float), expected, err_msg=column
        )


@pytest.mark.parametrize("tf", HTF)
def test_bars_inside_an_open_htf_bar_do_not_reach_its_earlier_values(
    tf: str, cfg: DictConfig
) -> None:
    bars = synthetic_m1()
    htf_index = resample(bars, tf).index  # type: ignore[arg-type]
    open_time, close_time = htf_index[3], htf_index[4]
    inside = (bars.index >= open_time) & (bars.index < close_time)
    perturbed = bars.copy()
    perturbed.loc[inside, PRICE] = perturbed.loc[inside, PRICE] * 1.2

    original = align_one(bars, tf, cfg)
    changed = align_one(perturbed, tf, cfg)
    columns = [c for c in original.columns if c.startswith(f"{tf}_")]
    assert columns
    before_close = bars.index < close_time
    pd.testing.assert_frame_equal(
        changed.loc[before_close, columns], original.loc[before_close, columns], check_exact=True
    )
    after = ~before_close
    assert not changed.loc[after, columns].equals(original.loc[after, columns])


# ---- declared output contract ---------------------------------------------------------------


def test_declared_outputs_are_float64_in_the_built_matrix(cfg: DictConfig) -> None:
    from features import build_features
    from market_data.arrow_schemas import mt5_export_to_bars

    example = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
    frame = pd.read_csv(example, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert problems == []
    bars: pd.DataFrame = table.select(
        ["event_time", "open", "high", "low", "close", "volume"]
    ).to_pandas()
    bars.index = pd.DatetimeIndex(bars.pop("event_time"))
    built = build_features(bars, cfg=cfg)
    wrong = {
        column.name: str(built[column.name].dtype)
        for node in registry_nodes(cfg.features)
        for column in node.outputs
        if column.name in built.columns and str(built[column.name].dtype) != column.dtype
    }
    assert wrong == {}
