"""Backend-neutral identity for stored artifact payloads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Logical artifact identity, independent of its storage location."""

    key: str
    media_type: str
    sha256: str


__all__ = ["ArtifactRef"]
