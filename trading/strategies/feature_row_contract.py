from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol


class FeatureRow(Protocol):
    """Expose the minimal time-indexed feature-row interface for strategies."""

    @property
    def index(self) -> Any:
        """Return the timestamp associated with this feature row.

        Returns:
            Result of return the timestamp associated with this feature row.
        """

    def get(self, key: str, default: Any = ...) -> Any:
        """Read a named feature and return a fallback when it is absent.

        Args:
            key: Feature name to look up.
            default: Value returned when the feature is absent.

        Returns:
            Feature value or the supplied default.
        """

    def __getitem__(self, key: str) -> float:
        """Process FeatureRow.

        Args:
            key: Text or path value identifying the key.

        Returns:
            Numeric result returned by ``__getitem__``.
        """
        ...

    def __iter__(self) -> Iterator[str]:
        """Iterate over feature names available on the row.

        Returns:
            Feature names in the row's source-column order.
        """
        ...

    def __contains__(self, key: object) -> bool:
        """Check whether a feature name is available on the row.

        Args:
            key: Value checked against the row's feature names.

        Returns:
            Whether the row contains the requested feature name.
        """
        ...
