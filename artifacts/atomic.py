from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _atomic_replace(path: Path, payload: bytes, *, new_file_mode: int | None = None) -> Path:
    """Process replace.

    Args:
        path: Path to the input file or directory.
        payload: Payload used by the operation described above.
        new_file_mode: New file mode used by the operation described above.

    Returns:
        Path returned by ``_atomic_replace``.
    """
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else new_file_mode
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return path


def write_text_atomic(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    new_file_mode: int | None = None,
) -> Path:
    """Write text by replacing the destination atomically.

    Args:
        path: Destination file.
        text: Complete text to write.
        encoding: Text encoding used for the temporary and destination files.
        new_file_mode: Optional permissions for a newly created destination.

    Returns:
        Path returned by ``write_text_atomic``.
    """
    return _atomic_replace(Path(path), text.encode(encoding), new_file_mode=new_file_mode)


def write_bytes_atomic(path: str | Path, payload: bytes) -> Path:
    """Atomically write opaque bytes while preserving the destination on failure.

    Args:
        path: Path to the input file or directory.
        payload: Payload used by the operation described above.

    Returns:
        Path returned by ``write_bytes_atomic``.
    """
    return _atomic_replace(Path(path), payload)


def write_json_atomic(
    path: str | Path,
    value: Any,
    *,
    default: Callable[[Any], Any] | None = str,
    new_file_mode: int | None = None,
) -> Path:
    """Atomically serialize JSON using the repository's canonical formatting.

    Pass ``default=None`` for strict JSON validation; the normal default keeps
    the historical string fallback used by metadata writers.

    Args:
        path: Path to the input file or directory.
        value: Value to process.
        default: Default used by the operation described above.
        new_file_mode: New file mode used by the operation described above.

    Returns:
        Path returned by ``write_json_atomic``.
    """
    return write_text_atomic(
        path,
        json.dumps(value, indent=2, sort_keys=True, default=default) + "\n",
        new_file_mode=new_file_mode,
    )
