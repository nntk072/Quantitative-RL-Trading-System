"""Append-only streaming state for recursive technical indicators (CAUSAL-FEATURE-GRAPH slice 1).

Each state consumes one finite bar or value at a time and returns a new immutable snapshot, so a
caller can resume from any prefix. The recursions match the batch definitions in
:mod:`features.technical.indicators`: EMA is ``ewm(span, adjust=False)`` and ATR is the
``ewm(alpha=1/period, adjust=False)`` mean of the true range against the previous close.

This slice covers EMA and ATR on finite inputs only. Missing values are refused rather than
carried forward. Window-based indicators, the registry integration and the checkpoint layout are
not implemented here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _require_finite(name: str, value: float) -> None:
    """Refuse a non-finite input so missing data is never carried into indicator state.

    Args:
        name: Field name used in the error message.
        value: Value to check.

    Raises:
        ValueError: If the value is NaN or infinite.
    """
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite for streaming indicator state, got {value!r}")


@dataclass(frozen=True, slots=True)
class RecursiveMeanState:
    """Snapshot of an exponentially weighted mean with ``adjust=False`` semantics.

    Attributes:
        alpha: Smoothing factor in (0, 1].
        value: Current mean, or None before the first observation.
        count: Number of observations consumed.
    """

    alpha: float
    value: float | None = None
    count: int = 0

    def __post_init__(self) -> None:
        """Validate the smoothing factor after construction."""
        if not (0.0 < self.alpha <= 1.0):
            raise ValueError(f"alpha must be in (0, 1], got {self.alpha!r}")
        if self.count < 0:
            raise ValueError("count must be non-negative")

    def update(self, x: float) -> RecursiveMeanState:
        """Return the state after consuming one finite observation.

        Args:
            x: Next observation.

        Returns:
            A new snapshot. This snapshot is unchanged.
        """
        _require_finite("observation", x)
        value = x if self.value is None else self.value + self.alpha * (x - self.value)
        return RecursiveMeanState(self.alpha, value, self.count + 1)


@dataclass(frozen=True, slots=True)
class StreamingEma:
    """Streaming EMA with the span convention of ``ewm(span=..., adjust=False)``.

    Attributes:
        span: Span in bars; alpha is ``2 / (span + 1)``.
        mean: Recursive mean snapshot.
    """

    span: int
    mean: RecursiveMeanState

    @classmethod
    def start(cls, span: int) -> StreamingEma:
        """Create an empty EMA state for a span.

        Args:
            span: Span in bars, at least 1.

        Returns:
            A state with no observations.

        Raises:
            ValueError: If span is below 1.
        """
        if span < 1:
            raise ValueError("span must be at least 1")
        return cls(span, RecursiveMeanState(alpha=2.0 / (span + 1)))

    def update(self, close: float) -> StreamingEma:
        """Return the state after one close.

        Args:
            close: Finite close price.

        Returns:
            A new snapshot.
        """
        return StreamingEma(self.span, self.mean.update(close))

    @property
    def value(self) -> float | None:
        """Current EMA after the consumed closes.

        Returns:
            The EMA value, or None before the first close.
        """
        return self.mean.value


@dataclass(frozen=True, slots=True)
class StreamingAtr:
    """Streaming ATR matching ``features.technical.indicators.atr``.

    Attributes:
        period: Smoothing period; alpha is ``1 / period``.
        prev_close: Close of the previous bar, or None before the first bar.
        mean: Recursive mean of the true range.
    """

    period: int
    prev_close: float | None
    mean: RecursiveMeanState

    @classmethod
    def start(cls, period: int) -> StreamingAtr:
        """Create an empty ATR state for a period.

        Args:
            period: Smoothing period, at least 1.

        Returns:
            A state with no bars.

        Raises:
            ValueError: If period is below 1.
        """
        if period < 1:
            raise ValueError("period must be at least 1")
        return cls(period, None, RecursiveMeanState(alpha=1.0 / period))

    def update(self, high: float, low: float, close: float) -> StreamingAtr:
        """Return the state after one completed bar.

        The first bar's true range is ``high - low``, as in the batch definition, because there is
        no previous close.

        Args:
            high: Bar high, finite.
            low: Bar low, finite and not above high.
            close: Bar close, finite.

        Returns:
            A new snapshot.

        Raises:
            ValueError: If an input is non-finite or the bar has low above high.
        """
        _require_finite("high", high)
        _require_finite("low", low)
        _require_finite("close", close)
        if low > high:
            raise ValueError("bar low must not exceed bar high")
        if self.prev_close is None:
            true_range = high - low
        else:
            true_range = max(high - low, abs(high - self.prev_close), abs(low - self.prev_close))
        return StreamingAtr(self.period, close, self.mean.update(true_range))

    @property
    def value(self) -> float | None:
        """Current ATR after the consumed bars.

        Returns:
            The ATR value, or None before the first bar.
        """
        return self.mean.value


__all__ = ["RecursiveMeanState", "StreamingAtr", "StreamingEma"]
