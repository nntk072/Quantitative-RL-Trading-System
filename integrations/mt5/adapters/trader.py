from abc import ABC, abstractmethod
from typing import Any


class Trader(ABC):
    """Broker-neutral interface for managing and sizing open positions."""

    @abstractmethod
    def open_position(self, *args: Any, **kwargs: Any) -> Any:
        """Open a position; returns the broker result object or None on failure.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of open a position; returns the broker result object or None on failure.
        """
        raise NotImplementedError

    @abstractmethod
    def close_positions(self, *args: Any, **kwargs: Any) -> Any:
        """Close positions selected by adapter-specific filters.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of close positions selected by adapter-specific filters.
        """
        raise NotImplementedError

    @abstractmethod
    def get_opened_positions(self, *args: Any, **kwargs: Any) -> Any:
        """Return open positions matching adapter-specific filters.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of return open positions matching adapter-specific filters.
        """
        raise NotImplementedError

    @abstractmethod
    def get_all_positions(self, *args: Any, **kwargs: Any) -> Any:
        """Return all positions visible through the adapter.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of return all positions visible through the adapter.
        """
        raise NotImplementedError

    @abstractmethod
    def send_to_break_even(self, *args: Any, **kwargs: Any) -> Any:
        """Adjust selected positions to their break-even stop level.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of adjust selected positions to their break-even stop level.
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_position_size(self, *args: Any, **kwargs: Any) -> Any:
        """Calculate a broker-compatible position size for a stop distance.

        Args:
            *args: Parsed command-line arguments for this operation.
            **kwargs: Kwargs used by the operation described above.

        Returns:
            Result of calculate a broker-compatible position size for a stop distance.
        """
        raise NotImplementedError
