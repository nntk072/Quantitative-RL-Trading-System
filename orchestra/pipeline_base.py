"""Typing bridge for phase mixins composed on the orchestra pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


class PipelineMixinBase:
    """Shared dependency surface and helpers consumed by phase mixins."""

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any:
            """Process PipelineMixinBase.

            Args:
                name: Name used to identify the requested file, artifact, or item.

            Returns:
                Result of process PipelineMixinBase.
            """
            ...
