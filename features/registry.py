"""Declared causal feature families (CAUSAL-FEATURE-GRAPH).

Outputs match ``build_features`` default columns; ``warmup_bars`` is the measured leading-null run.
Undeclared: HTF structure/BOS and opt-in blocks (PO3, FVG/IFVG, SMT, order blocks, liquidity).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

from omegaconf import DictConfig, OmegaConf

from features.graph import FeatureNode, OutputColumn, implementation_hash
from features.pipeline.session_context_features import ensure_london_atr_distances
from features.technical import indicators as ind
from features.technical import structure as struct
from features.technical import swings as sw
from market_data.transforms.activity import activity_series

PRIMARY = "M1"
BAR_COLUMNS = ("open", "high", "low", "close", "volume")
TECHNICAL = (
    "ema",
    "macd",
    "rsi",
    "atr",
    "adx",
    "bollinger",
    "stochastic",
    "returns",
    "realized_vol",
    "time",
    "atr_norm",
)
# fmt: off
STRUCTURE = ("last_swing_high", "last_swing_low", "dist_to_last_high_atr", "dist_to_last_low_atr",
             "dist_to_nearest_swing_atr", "last_swing_side", "last_swing_size_atr",
             "bars_since_last_swing", "hh", "hl", "lh", "ll", "swing_high_event", "swing_low_event",
             *(f"swing_{side}_{i}" for i in (1, 2, 3) for side in ("high", "low")))
SESSION = ("asian_high", "asian_low", "london_high", "london_low", "prev_day_close")
# Implementation functions per family; their source is hashed into node identity.
IMPLEMENTATIONS: dict[str, tuple[Callable[..., Any], ...]] = {
    "ema": (ind.build_indicators, ind.ema, ind.ema_features),
    "macd": (ind.build_indicators, ind.ema, ind.macd),
    "rsi": (ind.build_indicators, ind.rsi),
    "atr": (ind.build_indicators, ind._true_range, ind.atr),
    "adx": (ind.build_indicators, ind._true_range, ind.adx),
    "bollinger": (ind.build_indicators, ind.bollinger),
    "stochastic": (ind.build_indicators, ind.stochastic),
    "returns": (ind.build_indicators, ind.returns),
    "realized_vol": (ind.build_indicators, ind.realized_vol),
    "time": (ind.build_indicators, ind.time_features),
    "atr_norm": (ind.build_indicators, ind._true_range, ind.atr, ind.atr_normalized_price),
    "structure": (struct.structure_levels, sw.detect_swings, sw.classify_structure,
                  sw.swing_features, sw.swing_history),
    "session_levels": (struct.detect_session_levels,),
    "prev_day_range": (struct.detect_session_levels,),
    "volume_spike": (ind.volume_spike, activity_series),
    "atr_5": (ind._true_range, ind.atr),
    "sweep_velocity": (ind.sweep_velocity,),
    "wick_ratio": (ind.wick_ratio,),
    "london_distance": (ensure_london_atr_distances,),
    "ny_session": (ind.ny_session_clock,),
}
# fmt: on
# Known defect, not fixed here (values must not change): detect_session_levels reindexes
# date-keyed previous-day highs/lows against a DatetimeIndex, so prev_day_high/low are all null.


_REPO_ROOT = Path(__file__).resolve().parents[1]
# Source trees whose bytes are part of the feature-cache identity. They cover the undeclared blocks
# (HTF structure, PO3, FVG, SMT, order blocks, liquidity) and the transforms on the build path, so an
# edit to any of them rebuilds the cache instead of reusing a stale matrix.
SOURCE_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "features",
    _REPO_ROOT / "market_data" / "transforms",
)


def _source_entries() -> Iterator[tuple[str, Path]]:
    """Yield (identity path, file) for each Python source under SOURCE_ROOTS, in sorted order.

    The identity path is relative to each root's parent, so the digest does not depend on where
    the checkout lives.

    Yields:
        Pairs of identity path and source file.
    """
    for root in SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path.relative_to(root.parent).as_posix(), path


def source_files() -> list[Path]:
    """Return the Python sources covered by the cache identity.

    Returns:
        Sorted source files under SOURCE_ROOTS.
    """
    return [path for _, path in _source_entries()]


def code_identity() -> str:
    """Return sha256 over every family's implementation hash and every covered source file.

    Configuration independent. The family hashes keep node identities precise; the file digest
    makes any edit to the feature build path, declared or not, invalidate the cache.

    Returns:
        Hex digest covering the declared families' source and the covered source files.
    """
    digest = hashlib.sha256()
    for family in sorted(IMPLEMENTATIONS):
        digest.update(family.encode())
        digest.update(implementation_hash(IMPLEMENTATIONS[family]).encode())
    for identity_path, path in _source_entries():
        digest.update(identity_path.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


Names = tuple[str, ...]


# fmt: off
def _node(family: str, tf: str, deps: Names, outputs: Names, warmup: int,
          config: Mapping[str, Any]) -> FeatureNode:
    """Build one bar-close feature node with float64 outputs and train-independent fit scope.

    Args:
        family: Feature family name, also the implementation lookup key.
        tf: Timeframe label the node belongs to (for example ``M1``).
        deps: Node ids this node depends on.
        outputs: Output column names, each stored as float64.
        warmup: Number of leading bars that are null before values are valid.
        config: Configuration values recorded in the node identity.

    Returns:
        The declared feature node.
    """
    return FeatureNode(node_id=f"{tf}.{family}", version="1", dependencies=deps,
                       required_columns=BAR_COLUMNS, timeframe=tf, warmup_bars=warmup,
                       availability="bar_close", fit_scope="none",
                       outputs=tuple(OutputColumn(n, "float64") for n in outputs),
                       config=config, implementation=IMPLEMENTATIONS.get(family, ()))
# fmt: on


def _technical(tf: str, f: Mapping[str, Any]) -> list[FeatureNode]:
    """Declare the eleven indicator families of ``build_indicators`` for one timeframe.

    Args:
        tf: Timeframe label used as the node id prefix.
        f: Plain ``features`` configuration mapping.

    Returns:
        One node per technical family, in ``TECHNICAL`` order.
    """
    periods = [int(p) for p in f["ema_periods"]]
    horizons = [int(h) for h in f["return_horizons"]]
    k, d = int(f["stoch_k"]), int(f["stoch_d"])
    prefix = "" if tf == PRIMARY else f"{tf}_"
    # family: (outputs, warmup bars, configuration); warmup is the measured leading-null run.
    # fmt: off
    specs: dict[str, tuple[tuple[str, ...], int, dict[str, Any]]] = {
        "ema": (tuple(f"ema_{p}{s}" for p in periods for s in ("", "_slope", "_dist")), 2, {"periods": periods}),
        "macd": (("macd", "macd_signal", "macd_hist"), 1, {"fast": f["macd_fast"], "slow": f["macd_slow"], "signal": f["macd_signal"]}),
        "rsi": (("rsi",), 5, {"period": f["rsi_period"]}),
        "atr": (("atr",), 1, {"period": f["atr_period"]}),
        "adx": (("adx", "plus_di", "minus_di"), 2 * int(f["adx_period"]), {"period": f["adx_period"]}),
        "bollinger": (("bb_pct_b", "bb_width", "bb_mid"), int(f["bb_period"]), {"period": f["bb_period"], "std": f["bb_std"]}),
        "stochastic": (("stoch_k", "stoch_d"), k + d - 1, {"k": k, "d": d}),
        "returns": (tuple(f"ret_{h}" for h in horizons), max(horizons) + 1, {"horizons": horizons}),
        "realized_vol": (("realized_vol",), int(f["realized_vol_period"]) + 1, {"period": f["realized_vol_period"]}),
        "time": (("tod_sin", "tod_cos", "dow_sin", "dow_cos"), 1, {}),
        "atr_norm": (("atr_norm_price",), 2, {"period": f["atr_period"]}),
    }
    # fmt: on
    nodes = []
    for family in TECHNICAL:
        outputs, warmup, config = specs[family]
        deps = (f"{tf}.bars", f"{tf}.atr") if family == "atr_norm" else (f"{tf}.bars",)
        nodes.append(_node(family, tf, deps, tuple(prefix + o for o in outputs), warmup, config))
    return nodes


def registry_nodes(features_cfg: DictConfig) -> list[FeatureNode]:
    """Declare every family for the given ``features`` configuration node.

    Args:
        features_cfg: The resolved ``features`` configuration node.

    Returns:
        Feature nodes for the primary timeframe and each higher timeframe.
    """
    f: dict[str, Any] = OmegaConf.to_container(features_cfg, resolve=True)  # type: ignore[assignment]
    bars = f"{PRIMARY}.bars"
    nodes = [_node("bars", PRIMARY, (), (), 0, {}), *_technical(PRIMARY, f)]
    # fmt: off
    m1: tuple[tuple[str, tuple[str, ...], tuple[str, ...], int, dict[str, Any]], ...] = (
        ("structure", (), STRUCTURE, 33, {}),
        ("session_levels", (), SESSION, 595, {}),
        ("prev_day_range", (), ("prev_day_high", "prev_day_low"), 0, {}),
        ("volume_spike", (), ("volume_spike",), 0, {"window": 20}),
        ("atr_5", (), ("atr_5",), 0, {"period": 5}),
        ("sweep_velocity", ("session_levels", "atr_5"), ("sweep_velocity_bullish", "sweep_velocity_bearish"), 595, {"atr_period": 5}),
        ("wick_ratio", (), ("wick_ratio",), 0, {}),
        ("london_distance", ("session_levels", "atr_5"), ("price_to_london_high_atr", "price_to_london_low_atr"), 595, {}),
        ("ny_session", (), ("ny_session_sin", "ny_session_cos", "ny_minutes_to_close"), 0, {}),
    )
    # fmt: on
    for family, extra, outputs, warmup, config in m1:
        deps = (bars, *(f"{PRIMARY}.{e}" for e in extra)) if extra else (bars,)
        nodes.append(_node(family, PRIMARY, deps, outputs, warmup, config))
    for tf in (str(t).upper() for t in f["htf_timeframes"]):
        nodes += [_node("bars", tf, (), (), 0, {}), *_technical(tf, f)]
    return nodes
