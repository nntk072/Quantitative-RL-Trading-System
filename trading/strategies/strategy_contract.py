"""Base interface for trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

import pandas as pd

from .feature_row_contract import FeatureRow


def columns_matching(columns: Iterable[object], stem: str) -> tuple[str, ...]:
    """Column names equal to ``stem`` or ending with ``_{stem}``.

    Args:
        columns: Items supplied for the columns, in input order.
        stem: Text or path value identifying the stem.

    Returns:
        Values returned by ``columns_matching``, in the declared order.
    """
    suffix = "_" + stem
    return tuple(str(col) for col in columns if str(col) == stem or str(col).endswith(suffix))


class TradingStrategy(ABC):
    """Strategy semantics consumed by :class:`TradingEnv`.

    Implementations must be stateless with respect to time: all methods
    receive the feature row of the decision bar and answer from it.
    """

    name: str = "base"

    manipulation_filter: str = "against"

    #: Feature columns that must exist in the feature matrix (Agent.md §11).
    required_features: tuple[str, ...] = ()

    #: Raw price-level columns kept for execution/risk but excluded from the
    #: model's normalised sequence observation (Agent.md §11).
    raw_columns: tuple[str, ...] = ()

    @abstractmethod
    def validate_entry(self, *, direction: int, row: pd.Series) -> bool:
        """Whether an entry in ``direction`` is allowed at this bar.

        Args:
            direction: Signed trade direction: 1 for long and -1 for short.
            row: Row index or record being processed.

        Returns:
            Whether validate entry meets the requested condition.
        """

    @abstractmethod
    def sl_reference(self, *, direction: int, row: FeatureRow | pd.Series) -> float | None:
        """Structural SL reference price, or None if unavailable/invalid.

        Args:
            direction: Signed trade direction: 1 for long and -1 for short.
            row: Row index or record being processed.

        Returns:
            Result of structural SL reference price, or None if unavailable/invalid.
        """

    @abstractmethod
    def target_candidates(self, *, direction: int, row: pd.Series) -> dict[str, float]:
        """Named take-profit candidate levels for the TP-target resolver.

        Args:
            direction: Signed trade direction: 1 for long and -1 for short.
            row: Row index or record being processed.

        Returns:
            Mapping from ``str`` keys to ``float`` values.
        """

    def bind_columns(self, columns: Iterable[object]) -> None:
        """Remember column positions once, when the environment is built.

        Args:
            columns: Items supplied for the columns, in input order.
        """

    def context_direction(self, row: pd.Series) -> int:  # noqa: ARG002
        """Intended trade side from HTF/PO3 context: -1, 0, or +1.

        Default is flat (hold). Strategy overlays override for trader actions.

        Args:
            row: Row index or record being processed.

        Returns:
            Numeric result returned by ``context_direction``.
        """
        return 0

    def sl_candidates(self, *, direction: int, row: pd.Series) -> list[tuple[str, float]]:  # noqa: ARG002
        """Named SL levels for the trader action ``sl_anchor`` picker.

        Default empty — baseline / non-trader modes keep ``sl_reference``.

        Args:
            direction: Signed trade direction: 1 for long and -1 for short.
            row: Row index or record being processed.

        Returns:
            Values returned by ``sl_candidates``, in the declared order.
        """
        return []
