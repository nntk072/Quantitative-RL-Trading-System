"""Exercise CUDA-graph capture orchestration and replay-cache logic on CPU with fake CUDA APIs.

These unit tests cover capture warmups, stream ordering, static input copies, cache keying, and
cloned outputs. Actual CUDA replay parity still requires a GPU.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, cast

import pytest
import torch

from learning.rl import feature_graph
from learning.rl.feature_graph import FeatureGraphCache, GraphedForwardCache


class _FakeGraph:
    """Replays a fixed transform from the static inputs into the static outputs."""

    def __init__(self, transform: Any) -> None:
        self.transform = transform
        self.replays = 0

    def replay(self) -> None:
        self.replays += 1
        self.transform()


class _CaptureGraph:
    def __init__(self) -> None:
        self.replays = 0

    def replay(self) -> None:
        self.replays += 1


class _FakeStream:
    def __init__(self) -> None:
        self.waited_for: list[Any] = []

    def wait_stream(self, stream: Any) -> None:
        self.waited_for.append(stream)


def _fake_cuda_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, Any, _CaptureGraph, list[None]]:
    side_stream = _FakeStream()
    current_stream = _FakeStream()
    graph = _CaptureGraph()
    synchronizations: list[None] = []
    monkeypatch.setattr(torch.cuda, "Stream", lambda: side_stream)
    monkeypatch.setattr(torch.cuda, "current_stream", lambda: current_stream)
    monkeypatch.setattr(torch.cuda, "stream", lambda _stream: nullcontext())
    monkeypatch.setattr(
        torch.cuda,
        "graph",
        lambda _graph, **_kwargs: nullcontext(),
    )
    monkeypatch.setattr(torch.cuda, "CUDAGraph", lambda: graph)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda: synchronizations.append(None))
    return side_stream, current_stream, graph, synchronizations


def _feature_capture_factory(captures: list[tuple[Any, ...]]) -> Any:
    def capture(self: FeatureGraphCache, obs: dict[str, torch.Tensor], extractor: Any) -> Any:
        captures.append((tuple(sorted(obs)), id(extractor)))
        inputs = {name: value.detach().clone() for name, value in obs.items()}
        output = torch.zeros_like(inputs["x"])

        def transform() -> None:
            output.copy_(inputs["x"] * 2.0)

        return feature_graph._Captured(
            graph=cast(Any, _FakeGraph(transform)), inputs=inputs, output=output
        )

    return capture


def test_feature_graph_cache_captures_once_per_shape_and_replays_fresh_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures: list[tuple[Any, ...]] = []
    monkeypatch.setattr(FeatureGraphCache, "_capture", _feature_capture_factory(captures))
    cache = FeatureGraphCache(run=lambda obs, extractor: obs["x"])
    extractor = object()

    first = cache({"x": torch.tensor([1.0, 2.0])}, extractor)
    second = cache({"x": torch.tensor([10.0, 20.0])}, extractor)

    assert torch.equal(first, torch.tensor([2.0, 4.0]))
    assert torch.equal(second, torch.tensor([20.0, 40.0]))
    assert len(captures) == 1
    replayed = cast(Any, next(iter(cache._captured.values())).graph)
    assert replayed.replays == 2


def test_feature_graph_cache_returns_a_fresh_tensor_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(FeatureGraphCache, "_capture", _feature_capture_factory([]))
    cache = FeatureGraphCache(run=lambda obs, extractor: obs["x"])
    extractor = object()

    first = cache({"x": torch.tensor([1.0])}, extractor)
    second = cache({"x": torch.tensor([3.0])}, extractor)

    assert first is not second
    assert torch.equal(first, torch.tensor([2.0]))


def test_feature_graph_cache_keys_captures_by_shape_and_extractor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures: list[tuple[Any, ...]] = []
    monkeypatch.setattr(FeatureGraphCache, "_capture", _feature_capture_factory(captures))
    cache = FeatureGraphCache(run=lambda obs, extractor: obs["x"])
    extractor = object()

    cache({"x": torch.zeros(2)}, extractor)
    cache({"x": torch.zeros(3)}, extractor)
    cache({"x": torch.zeros(2)}, object())

    assert len(captures) == 3


def _graphed_capture_factory(captures: list[tuple[Any, ...]]) -> Any:
    def capture(
        self: GraphedForwardCache, obs: dict[str, torch.Tensor], extra: tuple[Any, ...]
    ) -> Any:
        captures.append(extra)
        inputs = {name: value.detach().clone() for name, value in obs.items()}
        outputs = (torch.zeros_like(inputs["x"]), torch.zeros_like(inputs["x"]))

        def transform() -> None:
            outputs[0].copy_(inputs["x"] + 1.0)
            outputs[1].copy_(inputs["x"] - 1.0)

        return feature_graph._CapturedForward(
            graph=cast(Any, _FakeGraph(transform)), inputs=inputs, outputs=outputs
        )

    return capture


def test_graphed_forward_cache_keys_on_extra_arguments_and_returns_all_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures: list[tuple[Any, ...]] = []
    monkeypatch.setattr(GraphedForwardCache, "_capture", _graphed_capture_factory(captures))
    cache = GraphedForwardCache(
        run=lambda obs, *extra: (obs["x"], obs["x"]),
        capture_context=nullcontext,
    )

    deterministic = cache({"x": torch.tensor([5.0])}, True)
    stochastic = cache({"x": torch.tensor([7.0])}, False)
    again = cache({"x": torch.tensor([9.0])}, True)

    assert len(deterministic) == 2
    assert torch.equal(deterministic[0], torch.tensor([6.0]))
    assert torch.equal(deterministic[1], torch.tensor([4.0]))
    assert torch.equal(stochastic[0], torch.tensor([8.0]))
    assert torch.equal(again[0], torch.tensor([10.0]))
    assert captures == [(True,), (False,)]


def test_feature_graph_capture_runs_warmup_and_capture_with_fake_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    side_stream, current_stream, graph, synchronizations = _fake_cuda_capture(monkeypatch)
    calls: list[bool] = []

    def run(obs: dict[str, torch.Tensor], _extractor: Any) -> torch.Tensor:
        calls.append(torch.is_grad_enabled())
        return obs["x"] * 2.0

    cache = FeatureGraphCache(run)
    obs = {"x": torch.tensor([2.0, 3.0])}
    extractor = object()

    captured = cache._capture(obs, extractor)

    assert calls == [False] * 4
    assert torch.equal(captured.output, torch.tensor([4.0, 6.0]))
    assert captured.inputs["x"].data_ptr() != obs["x"].data_ptr()
    assert cast(Any, captured.graph) is graph
    assert side_stream.waited_for == [current_stream]
    assert current_stream.waited_for == [side_stream]
    assert synchronizations == []


def test_graphed_forward_capture_runs_warmup_and_capture_with_fake_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    side_stream, current_stream, graph, synchronizations = _fake_cuda_capture(monkeypatch)
    events: list[tuple[Any, ...]] = []

    def run(obs: dict[str, torch.Tensor], *extra: Any) -> tuple[torch.Tensor, ...]:
        events.append(("run", extra, torch.is_grad_enabled()))
        return (obs["x"] + float(extra[0]), obs["x"] * 3.0)

    class _CaptureContext:
        def __enter__(self) -> None:
            events.append(("enter",))

        def __exit__(self, *_args: Any) -> None:
            events.append(("exit",))

    def capture_context() -> _CaptureContext:
        return _CaptureContext()

    cache = GraphedForwardCache(run, capture_context)
    obs = {"x": torch.tensor([2.0, 3.0])}

    captured = cache._capture(obs, (1.0,))

    assert events[0] == ("enter",)
    assert events[1:-1] == [("run", (1.0,), False)] * 4
    assert events[-1] == ("exit",)
    assert torch.equal(captured.outputs[0], torch.tensor([3.0, 4.0]))
    assert torch.equal(captured.outputs[1], torch.tensor([6.0, 9.0]))
    assert captured.inputs["x"].data_ptr() != obs["x"].data_ptr()
    assert cast(Any, captured.graph) is graph
    assert side_stream.waited_for == [current_stream]
    assert current_stream.waited_for == [side_stream]
    assert synchronizations == [None]
