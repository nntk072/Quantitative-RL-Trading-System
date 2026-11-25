"""Per-file SHA-256 index and verification for stored artifact trees.

The index lists every regular file under an artifact root with its size and
SHA-256. Verification refuses a missing, altered, unlisted, or escaping file
with a typed error. The index itself is written atomically and is never
listed in itself.
"""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from .atomic import write_json_atomic
from .identity import file_sha256

INDEX_NAME = "files.json"
_SCHEMA_VERSION = 1


class ArtifactIntegrityError(ValueError):
    """An artifact tree does not match its file index."""


class ArtifactFileMissingError(ArtifactIntegrityError):
    """A file named by the index, or the index itself, is absent."""


class ArtifactChecksumError(ArtifactIntegrityError):
    """A listed file's size or SHA-256 differs from the index."""


def _tree_files(root: Path, name: str) -> dict[str, Path]:
    """Map relative POSIX paths to regular files below ``root``, excluding ``name``.

    Args:
        root: Artifact root directory.
        name: Index filename to exclude.

    Returns:
        Mapping from relative POSIX path to absolute file path.
    """
    found: dict[str, Path] = {}
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        for entry in (*dirnames, *filenames):
            path = Path(current, entry)
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise ArtifactIntegrityError(f"symbolic link not allowed in artifact: {relative}")
            if path.is_file():
                if relative != name:
                    found[relative] = path
            elif not path.is_dir():
                raise ArtifactIntegrityError(f"unsupported entry in artifact: {relative}")
    return found


def _safe_relative(relative: str, name: str) -> None:
    """Reject index entries that could address a path outside the artifact.

    Args:
        relative: Relative path read from the index.
        name: Index filename, which may not list itself.
    """
    parts = PurePosixPath(relative).parts
    if not relative or PurePosixPath(relative).is_absolute() or ".." in parts or relative == name:
        raise ArtifactIntegrityError(f"unsafe path in file index: {relative!r}")


def write_file_index(root: str | Path, *, name: str = INDEX_NAME) -> Path:
    """Record the exact regular files under ``root`` with their size and SHA-256.

    Args:
        root: Artifact root directory.
        name: Index filename written inside ``root``.

    Returns:
        Path to the written index.
    """
    base = Path(root)
    files: dict[str, dict[str, Any]] = {
        relative: {"sha256": file_sha256(path), "size": path.stat().st_size}
        for relative, path in _tree_files(base, name).items()
    }
    return write_json_atomic(base / name, {"schema_version": _SCHEMA_VERSION, "files": files})


def verify_file_index(root: str | Path, *, name: str = INDEX_NAME) -> dict[str, Path]:
    """Verify that ``root`` holds exactly the files its index lists, unaltered.

    Args:
        root: Artifact root directory.
        name: Index filename inside ``root``.

    Returns:
        Mapping from each indexed relative path to its absolute file path.

    Raises:
        ArtifactFileMissingError: The index or a listed file is absent.
        ArtifactChecksumError: A listed file's size or SHA-256 differs.
        ArtifactIntegrityError: The index is malformed, unsafe, or unlisted files exist.
    """
    base = Path(root)
    index_path = base / name
    if not index_path.is_file():
        raise ArtifactFileMissingError(f"file index is missing: {name}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != _SCHEMA_VERSION
        or not isinstance(data.get("files"), dict)
    ):
        raise ArtifactIntegrityError("file index has an invalid shape")
    listed = data["files"]

    present = _tree_files(base, name)
    resolved: dict[str, Path] = {}
    for relative, expected in listed.items():
        _safe_relative(relative, name)
        if relative not in present:
            raise ArtifactFileMissingError(f"listed file is missing: {relative}")
        path = present[relative]
        if (
            not isinstance(expected, dict)
            or path.stat().st_size != expected.get("size")
            or file_sha256(path) != expected.get("sha256")
        ):
            raise ArtifactChecksumError(f"checksum mismatch for listed file: {relative}")
        resolved[relative] = path

    unlisted = sorted(set(present) - set(listed))
    if unlisted:
        raise ArtifactIntegrityError(f"unlisted files in artifact: {', '.join(unlisted)}")
    return resolved
