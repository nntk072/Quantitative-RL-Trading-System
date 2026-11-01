from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepositoryPaths:
    """Canonical repository locations derived from one root directory.

    Attributes:
        root: Repository root.
        config: Configuration directory.
        data: Input data directory.
        cache: Derived-data cache directory.
        outputs: Run output directory.
        logs: Log directory.
        baseline: Baseline artifact directory.
    """

    root: Path
    config: Path
    data: Path
    cache: Path
    outputs: Path
    logs: Path
    baseline: Path

    @classmethod
    def from_root(cls, root: str | Path) -> RepositoryPaths:
        """Resolve canonical repository paths beneath a root.

        Args:
            root: Repository directory to use as the path anchor.

        Returns:
            Paths for configuration, data, cache, outputs, logs, and baselines.
        """
        resolved = Path(root).expanduser().resolve()
        return cls(
            resolved,
            resolved / "config",
            resolved / "data",
            resolved / "cache",
            resolved / "outputs",
            resolved / "logs",
            resolved / "baseline",
        )


def repository_root(anchor: str | Path | None = None) -> Path:
    """Find the repository root by walking upward to ``pyproject.toml``.

    Args:
        anchor: Anchor used by the operation described above.

    Returns:
        Path returned by ``repository_root``.
    """
    start = Path(anchor).resolve() if anchor is not None else Path.cwd().resolve()
    if start.is_file():
        start = start.parent
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError(f"could not locate repository root from {start}")
