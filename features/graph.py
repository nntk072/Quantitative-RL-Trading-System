"""Typed causal feature-node contract: structural validation, order and content hashes.

Pure Python and offline. A node's hash changes when its definition, configuration,
timeframe source hash or any upstream hash changes, and not when an unrelated node changes.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from graphlib import CycleError as GraphCycleError
from graphlib import TopologicalSorter
from typing import Any, Literal

FitScope = Literal["none", "train_only"]
_FIT_SCOPES: frozenset[str] = frozenset({"none", "train_only"})


class FeatureGraphError(ValueError):
    """Base class for feature-graph refusals."""


class DuplicateNodeError(FeatureGraphError):
    """Two nodes share a node_id."""


class MissingDependencyError(FeatureGraphError):
    """A node depends on a node_id that is not in the graph."""


class DuplicateOutputError(FeatureGraphError):
    """Two outputs, possibly from one node, share a column name."""


class CycleError(FeatureGraphError):
    """The dependency relation contains a cycle, including a self-loop."""


class FitScopeError(FeatureGraphError):
    """A train_only node would be fit on rows after the training cutoff."""


@dataclass(frozen=True)
class OutputColumn:
    """One output column name with its dtype string."""

    name: str
    dtype: str


@dataclass(frozen=True)
class FeatureNode:
    """Definition of one causal feature node."""

    node_id: str
    version: str
    dependencies: tuple[str, ...]
    required_columns: tuple[str, ...]
    timeframe: str
    warmup_bars: int
    availability: str
    outputs: tuple[OutputColumn, ...]
    fit_scope: FitScope
    config: Mapping[str, Any]
    # Functions that implement the node; their source text is part of the node identity.
    implementation: tuple[Callable[..., Any], ...] = ()

    def __post_init__(self) -> None:
        """Validate scalar fields and copy the configuration mapping."""
        if not self.node_id:
            raise FeatureGraphError("node_id must be non-empty")
        if self.fit_scope not in _FIT_SCOPES:
            raise FeatureGraphError(f"{self.node_id!r}: unknown fit_scope {self.fit_scope!r}")
        if self.warmup_bars < 0:
            raise FeatureGraphError(f"{self.node_id!r}: warmup_bars must be >= 0")
        object.__setattr__(self, "config", dict(self.config))


def implementation_hash(functions: Sequence[Callable[..., Any]]) -> str:
    """Return sha256 over the qualified name and source text of each function, in order.

    The source is read at hash time, so an edit to a function body changes the hash.
    """
    digest = hashlib.sha256()
    for function in functions:
        digest.update(getattr(function, "__qualname__", repr(function)).encode())
        digest.update(inspect.getsource(function).encode())
    return digest.hexdigest()


def _topological_order(nodes: Mapping[str, FeatureNode]) -> tuple[str, ...]:
    """Return a deterministic order: ready layers, each sorted by node_id.

    Args:
        nodes: Mapping from node_id to FeatureNode.

    Returns:
        Node ids in dependency order.
    """
    sorter = TopologicalSorter({nid: set(nodes[nid].dependencies) for nid in sorted(nodes)})
    try:
        sorter.prepare()
    except GraphCycleError as exc:
        raise CycleError(f"dependency cycle {exc.args[1]}") from exc
    order: list[str] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        order.extend(ready)
        sorter.done(*ready)
    return tuple(order)


class FeatureGraph:
    """Validated feature DAG with deterministic order and per-node content hashes."""

    def __init__(self, nodes: Sequence[FeatureNode]) -> None:
        """Validate duplicates, dependencies, output names and acyclicity.

        Args:
            nodes: Feature nodes to validate and order.
        """
        by_id: dict[str, FeatureNode] = {}
        for node in nodes:
            if node.node_id in by_id:
                raise DuplicateNodeError(f"duplicate node_id {node.node_id!r}")
            by_id[node.node_id] = node
        owners: dict[str, str] = {}
        for node in nodes:
            for column in node.outputs:
                if column.name in owners:
                    raise DuplicateOutputError(
                        f"output {column.name!r} produced by {owners[column.name]!r} "
                        f"and {node.node_id!r}"
                    )
                owners[column.name] = node.node_id
            missing = sorted({d for d in node.dependencies if d not in by_id})
            if missing:
                raise MissingDependencyError(f"{node.node_id!r} needs missing {missing}")
        self._nodes = by_id
        self._order = _topological_order(by_id)

    @property
    def order(self) -> tuple[str, ...]:
        """Return the deterministic topological order of the node ids.

        Returns:
            Node ids in dependency order.
        """
        return self._order

    def content_hashes(self, source_hashes: Mapping[str, str]) -> dict[str, str]:
        """Return a sha256 hash per node from its definition, source, config and upstream.

        Args:
            source_hashes: Source data hash per timeframe.

        Returns:
            Mapping from node_id to hex digest.
        """
        hashes: dict[str, str] = {}
        for nid in self._order:
            node = self._nodes[nid]
            if node.timeframe not in source_hashes:
                raise FeatureGraphError(f"{nid!r}: no source hash for {node.timeframe!r}")
            deps = sorted(set(node.dependencies))
            payload = {
                "node_id": nid,
                "version": node.version,
                "dependencies": deps,
                "required_columns": list(node.required_columns),
                "timeframe": node.timeframe,
                "warmup_bars": node.warmup_bars,
                "availability": node.availability,
                "outputs": [[c.name, c.dtype] for c in node.outputs],
                "fit_scope": node.fit_scope,
                "config": node.config,
                "source_hash": source_hashes[node.timeframe],
                "upstream": {d: hashes[d] for d in deps},
                "implementation": implementation_hash(node.implementation),
            }
            # json.dumps raises TypeError for non-JSON configuration values.
            text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
            hashes[nid] = hashlib.sha256(text.encode()).hexdigest()
        return hashes


def assert_train_only_fit(node: FeatureNode, fit_times: Sequence[int], train_cutoff: int) -> None:
    """Refuse a train-only fit whose rows are later than the training cutoff.

    Args:
        node: Feature node being fit.
        fit_times: Timestamps of the rows used to fit.
        train_cutoff: Last timestamp allowed for training.
    """
    if node.fit_scope != "train_only" or not fit_times:
        return
    latest = max(fit_times)
    if latest > train_cutoff:
        raise FitScopeError(
            f"{node.node_id!r}: fit row at {latest} is after training cutoff {train_cutoff}"
        )
