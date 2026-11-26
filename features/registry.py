"""Declared causal feature families (CAUSAL-FEATURE-GRAPH).

Outputs match ``build_features`` default columns; ``warmup_bars`` is the measured leading-null run.
Undeclared: HTF structure/BOS and opt-in blocks (PO3, FVG/IFVG, SMT, order blocks, liquidity).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from omegaconf import DictConfig, OmegaConf

from features import source_identity
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


_REPO_ROOT = Path(__file__).resolve().parents[1]
# Seed source trees of the feature build. The identity also covers every project module these
# import (PO3, FVG, SMT, order blocks, decisioning/trade_setup, market_data loaders, artifacts), so
# an edit to any of them rebuilds the cache instead of reusing a stale matrix.
SOURCE_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "features",
    _REPO_ROOT / "market_data" / "transforms",
)


def source_files() -> list[Path]:
    """Return the Python sources covered by the cache identity.

    Returns:
        Sorted source files: the seed trees under SOURCE_ROOTS and every project module they import.
    """
    return list(source_identity.source_files(SOURCE_ROOTS, _REPO_ROOT))


def code_identity() -> str:
    """Return sha256 over the declared family implementations and the whole build-path source.

    The per-family hashes name the declared nodes. The build-path digest covers every module the
    feature build can execute, so an edit to an undeclared block also changes the cache key.
    Configuration is not part of this identity.

    Returns:
        Hex digest of the declared family implementations and build-path source.
    """
    digest = hashlib.sha256()
    for family in sorted(IMPLEMENTATIONS):
        digest.update(family.encode())
        digest.update(implementation_hash(IMPLEMENTATIONS[family]).encode())
    digest.update(source_identity.code_digest(SOURCE_ROOTS, _REPO_ROOT).encode())
    return digest.hexdigest()


Names = tuple[str, ...]
# (output name, units) pairs, in column order.
Columns = tuple[tuple[str, str], ...]
# Units of the non-technical M1 outputs. An output missing here fails the registry build.
UNIT_OF: dict[str, str] = {
    "last_swing_high": "price",
    "last_swing_low": "price",
    "dist_to_last_high_atr": "atr_multiple",
    "dist_to_last_low_atr": "atr_multiple",
    "dist_to_nearest_swing_atr": "atr_multiple",
    "last_swing_side": "direction",
    "last_swing_size_atr": "atr_multiple",
    "bars_since_last_swing": "bars",
    "hh": "flag",
    "hl": "flag",
    "lh": "flag",
    "ll": "flag",
    "swing_high_event": "flag",
    "swing_low_event": "flag",
    **{f"swing_{side}_{i}": "price" for side in ("high", "low") for i in (1, 2, 3)},
    "asian_high": "price",
    "asian_low": "price",
    "london_high": "price",
    "london_low": "price",
    "prev_day_close": "price",
    "prev_day_high": "price",
    "prev_day_low": "price",
    "volume_spike": "ratio",
    "atr_5": "price",
    "sweep_velocity_bullish": "atr_multiple",
    "sweep_velocity_bearish": "atr_multiple",
    "wick_ratio": "ratio",
    "price_to_london_high_atr": "atr_multiple",
    "price_to_london_low_atr": "atr_multiple",
    "ny_session_sin": "unit_circle",
    "ny_session_cos": "unit_circle",
    "ny_minutes_to_close": "unit_interval",
}


def _columns(names: Names) -> Columns:
    """Pair non-technical output names with their declared units.

    Args:
        names: Output names of one family.

    Returns:
        ``(name, units)`` pairs in the given order.
    """
    return tuple((name, UNIT_OF[name]) for name in names)


# fmt: off
def _node(family: str, tf: str, deps: Names, outputs: Columns, warmup: int,
          config: Mapping[str, Any], validity: str = "finite_after_warmup") -> FeatureNode:
    """Build one bar-close feature node with float64 outputs and train-independent fit scope.

    Args:
        family: Feature family name, also the implementation lookup key.
        tf: Timeframe label the node belongs to (for example ``M1``).
        deps: Node ids this node depends on.
        outputs: ``(name, units)`` pairs, each stored as float64.
        warmup: Number of leading bars that are null before values are valid.
        config: Configuration values recorded in the node identity.
        validity: Validity policy from ``VALIDITY_POLICIES``.

    Returns:
        The declared feature node.
    """
    return FeatureNode(node_id=f"{tf}.{family}", version="1", dependencies=deps,
                       required_columns=BAR_COLUMNS, timeframe=tf, warmup_bars=warmup,
                       availability="bar_close", validity=validity, fit_scope="none",
                       outputs=tuple(OutputColumn(n, "float64", u) for n, u in outputs),
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
    # family: (outputs with units, warmup bars, configuration); warmup is the measured leading-null run.
    # fmt: off
    specs: dict[str, tuple[Columns, int, dict[str, Any]]] = {
        "ema": (tuple(c for p in periods for c in ((f"ema_{p}", "price"), (f"ema_{p}_slope", "price_per_bar"), (f"ema_{p}_dist", "ratio"))), 2, {"periods": periods}),
        "macd": ((("macd", "price"), ("macd_signal", "price"), ("macd_hist", "price")), 1, {"fast": f["macd_fast"], "slow": f["macd_slow"], "signal": f["macd_signal"]}),
        "rsi": ((("rsi", "percent"),), 5, {"period": f["rsi_period"]}),
        "atr": ((("atr", "price"),), 1, {"period": f["atr_period"]}),
        "adx": ((("adx", "percent"), ("plus_di", "percent"), ("minus_di", "percent")), 2 * int(f["adx_period"]), {"period": f["adx_period"]}),
        "bollinger": ((("bb_pct_b", "ratio"), ("bb_width", "ratio"), ("bb_mid", "price")), int(f["bb_period"]), {"period": f["bb_period"], "std": f["bb_std"]}),
        "stochastic": ((("stoch_k", "percent"), ("stoch_d", "percent")), k + d - 1, {"k": k, "d": d}),
        "returns": (tuple((f"ret_{h}", "log_return") for h in horizons), max(horizons) + 1, {"horizons": horizons}),
        "realized_vol": ((("realized_vol", "log_return_stdev"),), int(f["realized_vol_period"]) + 1, {"period": f["realized_vol_period"]}),
        "time": ((("tod_sin", "unit_circle"), ("tod_cos", "unit_circle"), ("dow_sin", "unit_circle"), ("dow_cos", "unit_circle")), 1, {}),
        "atr_norm": ((("atr_norm_price", "atr_multiple"),), 2, {"period": f["atr_period"]}),
    }
    # fmt: on
    nodes = []
    for family in TECHNICAL:
        outputs, warmup, config = specs[family]
        deps = (f"{tf}.bars", f"{tf}.atr") if family == "atr_norm" else (f"{tf}.bars",)
        prefixed = tuple((prefix + name, units) for name, units in outputs)
        nodes.append(_node(family, tf, deps, prefixed, warmup, config))
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
        # The previous-day levels are null only until the first day completes, not for a bar count.
        validity = "finite_after_prior_day" if family == "prev_day_range" else "finite_after_warmup"
        nodes.append(_node(family, PRIMARY, deps, _columns(outputs), warmup, config, validity))
    for tf in (str(t).upper() for t in f["htf_timeframes"]):
        nodes += [_node("bars", tf, (), (), 0, {}), *_technical(tf, f)]
    return nodes
