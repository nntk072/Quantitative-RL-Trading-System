"""Feature registry: nodes resolve against the real build path, and the cache key tracks code.

Uses the tracked example bars only (CAUSAL-FEATURE-GRAPH).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest
from omegaconf import DictConfig

from configuration.configuration_loader import load_config
from features import build_features, feature_cache_content_hash
from features.graph import FeatureGraph, FeatureNode
from features.registry import IMPLEMENTATIONS, code_identity, registry_nodes
from features.technical import indicators as ind
from market_data.arrow_schemas import mt5_export_to_bars

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
# Structure/BOS block of higher timeframes is produced by build_features but not declared yet.
UNDECLARED_HTF_STRUCTURE = (
    "last_swing_high",
    "last_swing_low",
    "bos_up",
    "bos_down",
    "dist_to_swing_high_atr",
    "dist_to_swing_low_atr",
)


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
def cfg() -> DictConfig:
    return load_config()


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    return load_example_bars()


@pytest.fixture(scope="module")
def nodes(cfg: DictConfig) -> list[FeatureNode]:
    return registry_nodes(cfg.features)


@pytest.fixture(scope="module")
def produced(bars: pd.DataFrame, cfg: DictConfig) -> set[str]:
    return set(build_features(bars, cfg=cfg).columns)


def test_every_node_resolves_and_the_graph_validates(nodes) -> None:
    graph = FeatureGraph(nodes)  # raises on duplicate ids, missing deps, duplicate outputs, cycles
    ids = {node.node_id for node in nodes}
    assert set(graph.order) == ids
    for node in nodes:
        assert set(node.dependencies) <= ids, node.node_id
    names = [column.name for node in nodes for column in node.outputs]
    assert len(names) == len(set(names))


def test_declared_outputs_are_exactly_the_columns_build_features_produces(nodes, produced) -> None:
    declared = {column.name for node in nodes for column in node.outputs}
    undeclared = {
        f"{tf}_{name}"
        for tf in ("M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
        for name in UNDECLARED_HTF_STRUCTURE
    }
    assert undeclared <= produced
    assert declared <= produced, sorted(declared - produced)
    assert produced - undeclared == declared, sorted(produced - undeclared - declared)


def test_code_identity_is_stable_and_cache_key_is_repeatable(bars, cfg) -> None:
    assert code_identity() == code_identity()
    assert feature_cache_content_hash(cfg, bars) == feature_cache_content_hash(cfg, bars)


def test_code_only_change_in_a_function_body_changes_its_node_and_the_cache_key(
    bars, cfg, nodes, monkeypatch
) -> None:
    before_key = feature_cache_content_hash(cfg, bars)
    before = FeatureGraph(nodes).content_hashes({tf: "src" for tf in {n.timeframe for n in nodes}})
    real_getsource = inspect.getsource

    def edited_getsource(obj: object) -> str:
        text = real_getsource(obj)  # type: ignore[arg-type]
        if getattr(obj, "__name__", "") == "rsi":
            text = text.replace("100 - (100 / (1 + rs))", "100 - (101 / (1 + rs))")
        return text

    monkeypatch.setattr(inspect, "getsource", edited_getsource)
    assert feature_cache_content_hash(cfg, bars) != before_key
    after = FeatureGraph(nodes).content_hashes({tf: "src" for tf in {n.timeframe for n in nodes}})
    changed = {nid for nid in before if before[nid] != after[nid]}
    assert changed == {n.node_id for n in nodes if n.node_id.endswith(".rsi")}


def test_swapping_a_family_implementation_changes_the_cache_key(bars, cfg, monkeypatch) -> None:
    before_key = feature_cache_content_hash(cfg, bars)
    before_identity = code_identity()
    monkeypatch.setitem(IMPLEMENTATIONS, "rsi", (ind.build_indicators, ind.ema))
    assert code_identity() != before_identity
    assert feature_cache_content_hash(cfg, bars) != before_key
