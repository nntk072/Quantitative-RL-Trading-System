"""Source identity of the feature build: digest of every repository module it can execute.

The feature cache key must change when any code on the build path changes, including
blocks that are not declared feature families (order blocks, PO3/FVG, pipeline stages).
Seed directories name the source trees that define the build. This module adds the
project-internal import closure of those seeds, found with a static AST pass that follows
absolute and relative imports, function-level imports, and the package ``__init__`` modules
that execute when a submodule is imported.

Identity paths are relative to the project root. A seed file outside the project root (only
possible for an overridden seed, such as a test fixture) is identified by its absolute path.

Parsed imports are memoized by (identity path, sha256 of the file content), so an edited file is
always re-parsed and an unchanged file is not.

Limits: imports computed at run time (``importlib`` with a variable name) are not followed.
Third-party and standard-library code is not digested; it is pinned by the environment lock.
"""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Default seed trees: the feature package and the market-data transforms it calls directly.
DEFAULT_SEED_DIRS: tuple[Path, ...] = (
    PROJECT_ROOT / "features",
    PROJECT_ROOT / "market_data" / "transforms",
)

# (identity path, sha256 of content) -> dotted names the file references.
_IMPORTS_BY_CONTENT: dict[tuple[str, str], frozenset[str]] = {}


def _identity(path: Path, project_root: Path) -> str:
    """Return the checkout-independent identity of a source file.

    Args:
        path: Source file.
        project_root: Project root that identity paths are relative to.

    Returns:
        Project-relative posix path, or the absolute posix path outside the project root.
    """
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _module_file(project_root: Path, dotted: str) -> Path | None:
    """Return the source file of a project module, or None when it is absent.

    Args:
        project_root: Project root that top-level module names are resolved against.
        dotted: Dotted module name such as ``features.pipeline.normalization``.

    Returns:
        Path to the ``.py`` file or package ``__init__.py``, or None.
    """
    parts = dotted.split(".")
    for candidate in (
        project_root.joinpath(*parts).with_suffix(".py"),
        project_root.joinpath(*parts, "__init__.py"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _package_of(project_root: Path, path: Path) -> list[str] | None:
    """Return the dotted package parts a module file belongs to.

    Args:
        project_root: Project root.
        path: Source file.

    Returns:
        Package name parts (``["pkg"]`` for ``pkg/__init__.py``), or None outside the root.
    """
    try:
        parts = list(path.relative_to(project_root).with_suffix("").parts)
    except ValueError:
        return None
    return parts if path.name == "__init__.py" else parts[:-1]


def _referenced_modules(project_root: Path, path: Path, source: str) -> set[str]:
    """Return dotted names that a source file imports, before project filtering.

    Args:
        project_root: Project root.
        path: Source file being scanned, used to resolve relative imports.
        source: Text of the file.

    Returns:
        Candidate dotted module names. Names outside the project are filtered by the caller.
    """
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = _package_of(project_root, path)
                if base is None or node.level - 1 > len(base):
                    continue
                base = base[: len(base) - (node.level - 1)]
                absolute = ".".join([*base, node.module] if node.module else base)
            else:
                absolute = node.module or ""
            if not absolute:
                continue
            names.add(absolute)
            # ``from pkg import name`` may import the submodule ``pkg.name``.
            names.update(f"{absolute}.{alias.name}" for alias in node.names if alias.name != "*")
    return names


def _imports_of(project_root: Path, path: Path, identity: str, data: bytes) -> frozenset[str]:
    """Return the referenced module names of a file, parsing only when its content is new.

    Args:
        project_root: Project root.
        path: Source file.
        identity: Identity path of the file.
        data: Bytes of the file, as read for the digest.

    Returns:
        Referenced dotted names for this exact file content at this identity.
    """
    key = (identity, hashlib.sha256(data).hexdigest())
    names = _IMPORTS_BY_CONTENT.get(key)
    if names is None:
        names = frozenset(_referenced_modules(project_root, path, data.decode("utf-8")))
        _IMPORTS_BY_CONTENT[key] = names
    return names


def _build_path_sources(seed_dirs: Sequence[Path], project_root: Path) -> dict[Path, bytes]:
    """Read every seed source file and every project module it imports, once each.

    Args:
        seed_dirs: Source trees that define the build.
        project_root: Project root that module names resolve against.

    Returns:
        Mapping from each source file on the build path to its bytes.
    """
    pending: list[Path] = []
    for seed in seed_dirs:
        pending.extend(sorted(p for p in seed.rglob("*.py") if "__pycache__" not in p.parts))
    # Only names rooted at a top-level project entry can resolve to a project file.
    top_level = {
        entry.stem for entry in project_root.iterdir() if entry.suffix == ".py" or entry.is_dir()
    }
    resolved: dict[str, Path | None] = {}
    sources: dict[Path, bytes] = {}
    for path in pending:
        sources[path] = path.read_bytes()
    queue = list(sources)
    while queue:
        current = queue.pop()
        identity = _identity(current, project_root)
        for dotted in _imports_of(project_root, current, identity, sources[current]):
            parts = dotted.split(".")
            if parts[0] not in top_level:
                continue
            # Importing a.b.c runs a/__init__.py, a/b/__init__.py and a/b/c.py.
            for depth in range(1, len(parts) + 1):
                name = ".".join(parts[:depth])
                if name not in resolved:
                    resolved[name] = _module_file(project_root, name)
                module = resolved[name]
                if module is not None and module not in sources:
                    sources[module] = module.read_bytes()
                    queue.append(module)
    return sources


def source_files(
    seed_dirs: Sequence[Path] = DEFAULT_SEED_DIRS,
    project_root: Path = PROJECT_ROOT,
) -> tuple[Path, ...]:
    """Return the sorted source files on the feature build path.

    Args:
        seed_dirs: Source trees that define the build.
        project_root: Project root for module resolution and identity paths.

    Returns:
        Seed files and every project module they import, transitively, sorted by identity.
    """
    sources = _build_path_sources(seed_dirs, project_root)
    return tuple(sorted(sources, key=lambda p: _identity(p, project_root)))


def code_digest(
    seed_dirs: Sequence[Path] = DEFAULT_SEED_DIRS,
    project_root: Path = PROJECT_ROOT,
) -> str:
    """Return a sha256 over the identity path and content of every build-path source file.

    Identity paths are relative to the project root, so the digest does not depend on where the
    checkout lives.

    Args:
        seed_dirs: Source trees that define the build.
        project_root: Project root for module resolution and identity paths.

    Returns:
        Hex digest of the build-path source.
    """
    sources = _build_path_sources(seed_dirs, project_root)
    digest = hashlib.sha256()
    for path in sorted(sources, key=lambda p: _identity(p, project_root)):
        digest.update(_identity(path, project_root).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(sources[path]).digest())
    return digest.hexdigest()


__all__ = ["DEFAULT_SEED_DIRS", "PROJECT_ROOT", "code_digest", "source_files"]
