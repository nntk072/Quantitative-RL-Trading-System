"""Typed feature-graph contract: refusals, deterministic order, content hashes, fit scope."""

from __future__ import annotations

from typing import Any

import pytest

from features.graph import (
    CycleError,
    DuplicateNodeError,
    DuplicateOutputError,
    FeatureGraph,
    FeatureGraphError,
    FeatureNode,
    FitScopeError,
    MissingDependencyError,
    OutputColumn,
    assert_train_only_fit,
)

SOURCES = {"M1": "src-m1-a", "H1": "src-h1-a"}


def node(
    node_id: str,
    deps: tuple[str, ...] = (),
    outputs: tuple[str, ...] | None = None,
    *,
    config: dict[str, Any] | None = None,
    timeframe: str = "M1",
    version: str = "1",
    fit_scope: str = "none",
) -> FeatureNode:
    names = outputs if outputs is not None else (f"{node_id}_out",)
    return FeatureNode(
        node_id=node_id,
        version=version,
        dependencies=deps,
        required_columns=("close",),
        timeframe=timeframe,
        warmup_bars=14,
        availability="bar_close",
        outputs=tuple(OutputColumn(name, "float64") for name in names),
        fit_scope=fit_scope,  # type: ignore[arg-type]
        config=config if config is not None else {"period": 14},
    )


def chain() -> list[FeatureNode]:
    return [node("a"), node("b", ("a",)), node("c", ("b", "a"))]


def test_cycle_is_refused() -> None:
    with pytest.raises(CycleError):
        FeatureGraph([node("a", ("c",)), node("b", ("a",)), node("c", ("b",))])


def test_self_loop_is_refused() -> None:
    with pytest.raises(CycleError):
        FeatureGraph([node("a", ("a",))])


def test_missing_dependency_is_refused() -> None:
    with pytest.raises(MissingDependencyError, match="ghost"):
        FeatureGraph([node("a"), node("b", ("ghost",))])


def test_duplicate_output_across_nodes_is_refused() -> None:
    with pytest.raises(DuplicateOutputError):
        FeatureGraph([node("a", outputs=("x",)), node("b", outputs=("x",))])


def test_duplicate_output_within_one_node_is_refused() -> None:
    with pytest.raises(DuplicateOutputError):
        FeatureGraph([node("a", outputs=("x", "x"))])


def test_duplicate_node_id_is_refused() -> None:
    with pytest.raises(DuplicateNodeError):
        FeatureGraph([node("a"), node("a", outputs=("other",))])


def test_typed_errors_share_a_base_class() -> None:
    assert issubclass(CycleError, FeatureGraphError)
    assert issubclass(MissingDependencyError, FeatureGraphError)
    assert issubclass(DuplicateOutputError, FeatureGraphError)


def test_order_respects_dependencies_and_is_deterministic() -> None:
    forward = FeatureGraph(chain()).order
    reverse = FeatureGraph(list(reversed(chain()))).order
    assert forward == reverse == ("a", "b", "c")
    diamond = FeatureGraph([node("z", ("a",)), node("m", ("a",)), node("a"), node("q", ("z", "m"))])
    assert diamond.order == ("a", "m", "z", "q")


def test_unknown_fit_scope_and_negative_warmup_are_refused() -> None:
    with pytest.raises(FeatureGraphError, match="fit_scope"):
        node("a", fit_scope="all_rows")
    with pytest.raises(FeatureGraphError, match="warmup"):
        FeatureNode(
            node_id="a",
            version="1",
            dependencies=(),
            required_columns=(),
            timeframe="M1",
            warmup_bars=-1,
            availability="bar_close",
            outputs=(),
            fit_scope="none",
            config={},
        )


def test_hash_is_stable_across_rebuilds() -> None:
    first = FeatureGraph(chain()).content_hashes(SOURCES)
    second = FeatureGraph(chain()).content_hashes(SOURCES)
    assert first == second
    assert len(set(first.values())) == 3


def test_hash_changes_on_own_config_change() -> None:
    base = FeatureGraph(chain()).content_hashes(SOURCES)
    changed = [node("a", config={"period": 20}), node("b", ("a",)), node("c", ("b", "a"))]
    after = FeatureGraph(changed).content_hashes(SOURCES)
    assert after["a"] != base["a"]


def test_hash_changes_on_upstream_change_including_transitive() -> None:
    base = FeatureGraph(chain()).content_hashes(SOURCES)
    # Changing "a" must change its downstream nodes "b" and "c" (transitively).
    changed = [node("a", config={"period": 20}), node("b", ("a",)), node("c", ("b", "a"))]
    after = FeatureGraph(changed).content_hashes(SOURCES)
    assert after["b"] != base["b"]
    assert after["c"] != base["c"]
    # Changing only the middle node leaves its upstream "a" hash unchanged.
    middle = [node("a"), node("b", ("a",), config={"k": 2}), node("c", ("b", "a"))]
    mid_after = FeatureGraph(middle).content_hashes(SOURCES)
    assert mid_after["a"] == base["a"]
    assert mid_after["b"] != base["b"]
    assert mid_after["c"] != base["c"]


def test_hash_changes_on_source_data_change_for_that_timeframe_only() -> None:
    graph = FeatureGraph([node("m1", timeframe="M1"), node("h1", timeframe="H1")])
    base = graph.content_hashes(SOURCES)
    changed = graph.content_hashes({**SOURCES, "M1": "src-m1-corrected"})
    assert changed["m1"] != base["m1"]
    assert changed["h1"] == base["h1"]


def test_hash_changes_on_version_bump() -> None:
    base = FeatureGraph(chain()).content_hashes(SOURCES)
    bumped = [node("a", version="2"), node("b", ("a",)), node("c", ("b", "a"))]
    assert FeatureGraph(bumped).content_hashes(SOURCES)["a"] != base["a"]


def test_no_hash_change_for_unrelated_node() -> None:
    base = FeatureGraph(chain() + [node("unrelated")]).content_hashes(SOURCES)
    changed = FeatureGraph(
        chain() + [node("unrelated", config={"period": 99}, outputs=("other",))]
    ).content_hashes(SOURCES)
    for nid in ("a", "b", "c"):
        assert changed[nid] == base[nid]
    assert changed["unrelated"] != base["unrelated"]


def test_missing_source_hash_for_timeframe_is_refused() -> None:
    graph = FeatureGraph([node("h1", timeframe="H1")])
    with pytest.raises(FeatureGraphError, match="H1"):
        graph.content_hashes({"M1": "src-m1-a"})


def test_non_json_config_is_refused() -> None:
    graph = FeatureGraph([node("a", config={"bad": object()})])
    with pytest.raises(TypeError):
        graph.content_hashes(SOURCES)


def test_train_only_fit_refuses_rows_after_cutoff() -> None:
    fitted = node("norm", fit_scope="train_only")
    with pytest.raises(FitScopeError):
        assert_train_only_fit(fitted, fit_times=[10, 20, 30], train_cutoff=25)


def test_train_only_fit_accepts_cutoff_later_than_fit_rows() -> None:
    fitted = node("norm", fit_scope="train_only")
    assert_train_only_fit(fitted, fit_times=[10, 20, 30], train_cutoff=30)
    assert_train_only_fit(fitted, fit_times=[10, 20, 30], train_cutoff=100)
    assert_train_only_fit(fitted, fit_times=[], train_cutoff=0)


def test_fit_scope_none_skips_cutoff_check() -> None:
    assert_train_only_fit(node("pure"), fit_times=[10**6], train_cutoff=0)
