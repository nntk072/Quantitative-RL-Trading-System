"""CUDA-graph replay of a policy's feature extractor for fixed-shape rollout batches."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

import torch

_WARMUP_ITERATIONS = 3


@dataclass
class _Captured:
    graph: torch.cuda.CUDAGraph
    inputs: dict[str, torch.Tensor]
    output: torch.Tensor


class FeatureGraphCache:
    """Capture one extractor forward per input shape and replay it with fresh inputs.

    The run callable must be free of host synchronisation and must read only the observation
    tensors it is given, so a replay reproduces an eager call exactly.
    """

    def __init__(self, run: Callable[[dict[str, torch.Tensor], Any], torch.Tensor]) -> None:
        """Store the eager forward that is captured.

        Args:
            run: Eager forward taking (observation tensors, feature extractor) and returning features.
        """
        self._run = run
        self._captured: dict[tuple[Any, ...], _Captured] = {}

    def __call__(self, obs: dict[str, torch.Tensor], extractor: Any) -> torch.Tensor:
        """Return features for ``obs`` by replaying the captured graph for its shapes.

        Args:
            obs: Observation tensors already on the CUDA device.
            extractor: Feature extractor the forward applies.

        Returns:
            A fresh tensor holding the features for ``obs``.
        """
        key = (
            id(extractor),
            tuple((name, tuple(value.shape)) for name, value in sorted(obs.items())),
        )
        captured = self._captured.get(key)
        if captured is None:
            captured = self._capture(obs, extractor)
            self._captured[key] = captured
        for name, buffer in captured.inputs.items():
            buffer.copy_(obs[name])
        captured.graph.replay()
        return captured.output.clone()

    def _capture(
        self, obs: dict[str, torch.Tensor], extractor: Any
    ) -> _Captured:  # pragma: no cover - needs CUDA graph capture
        """Record the eager forward into a CUDA graph with private static inputs.

        Args:
            obs: Observation tensors whose shapes the graph is fixed to.
            extractor: Feature extractor the forward applies.

        Returns:
            The captured graph with its static input and output buffers.
        """
        inputs = {name: value.detach().clone() for name, value in obs.items()}
        side_stream = torch.cuda.Stream()  # type: ignore[no-untyped-call]
        side_stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side_stream), torch.no_grad():
            for _ in range(_WARMUP_ITERATIONS):
                self._run(inputs, extractor)
        torch.cuda.current_stream().wait_stream(side_stream)
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, capture_error_mode="thread_local"), torch.no_grad():
            output = self._run(inputs, extractor)
        return _Captured(graph=graph, inputs=inputs, output=output)


__all__ = ["FeatureGraphCache", "GraphedForwardCache"]


@dataclass
class _CapturedForward:
    graph: torch.cuda.CUDAGraph
    inputs: dict[str, torch.Tensor]
    outputs: tuple[torch.Tensor, ...]


class GraphedForwardCache:
    """Capture a forward that returns a tuple of tensors, once per input shape and extra key.

    The run callable receives the static observation tensors followed by the extra arguments.
    ``capture_context`` is entered around warm-up and capture, so the caller can turn off checks
    that would force host syncs.
    """

    def __init__(
        self,
        run: Callable[..., tuple[torch.Tensor, ...]],
        capture_context: Callable[[], AbstractContextManager[None]],
    ) -> None:
        """Store the forward to capture and the context used while capturing it.

        Args:
            run: Forward taking (observation tensors, *extra) and returning a tuple of tensors.
            capture_context: Factory for the context entered around warm-up and capture.
        """
        self._run = run
        self._capture_context = capture_context
        self._captured: dict[tuple[Any, ...], _CapturedForward] = {}

    def __call__(self, obs: dict[str, torch.Tensor], *extra: Any) -> tuple[torch.Tensor, ...]:
        """Replay the captured forward for these shapes and extra arguments.

        Args:
            obs: Observation tensors already on the CUDA device.
            *extra: Hashable extra arguments, such as the deterministic flag.

        Returns:
            Fresh tensors holding the forward's outputs.
        """
        key = (tuple((name, tuple(value.shape)) for name, value in sorted(obs.items())), extra)
        captured = self._captured.get(key)
        if captured is None:
            captured = self._capture(obs, extra)
            self._captured[key] = captured
        for name, buffer in captured.inputs.items():
            buffer.copy_(obs[name])
        captured.graph.replay()
        return tuple(output.clone() for output in captured.outputs)

    def _capture(
        self, obs: dict[str, torch.Tensor], extra: tuple[Any, ...]
    ) -> _CapturedForward:  # pragma: no cover - needs CUDA graph capture
        """Record the forward into a CUDA graph with private static inputs.

        Args:
            obs: Observation tensors whose shapes the graph is fixed to.
            extra: Extra arguments passed to the run callable.

        Returns:
            The captured graph with its static inputs and outputs.
        """
        inputs = {name: value.detach().clone() for name, value in obs.items()}
        side_stream = torch.cuda.Stream()  # type: ignore[no-untyped-call]
        side_stream.wait_stream(torch.cuda.current_stream())
        with self._capture_context(), torch.no_grad():
            with torch.cuda.stream(side_stream):
                for _ in range(_WARMUP_ITERATIONS):
                    self._run(inputs, *extra)
            torch.cuda.current_stream().wait_stream(side_stream)
            graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(graph, capture_error_mode="thread_local"):
                outputs = self._run(inputs, *extra)
        torch.cuda.synchronize()
        return _CapturedForward(graph=graph, inputs=inputs, outputs=tuple(outputs))
