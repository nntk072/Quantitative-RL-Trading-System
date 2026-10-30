from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from artifacts.atomic import write_json_atomic

from .manifest import ArtifactManifest
from .retention import RetentionClass


@dataclass(frozen=True, slots=True)
class BaselineValidation:
    """Validation evidence returned only after every promotion check passes."""

    command: str
    checks: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.command.strip():
            raise ValueError("baseline validation evidence must record its command")
        if not self.checks or any(not check.strip() for check in self.checks):
            raise ValueError("baseline validation evidence must list the checks that passed")

    def to_dict(self) -> dict[str, object]:
        return {"accepted": True, "command": self.command, "checks": list(self.checks)}


Validator = Callable[[Path], BaselineValidation]


def _payload_sha256(path: Path) -> str:
    """Hash a staged file or directory tree, including names and symlink targets."""
    digest = hashlib.sha256()

    def add_field(value: bytes) -> None:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)

    if path.is_file():
        add_field(b"file")
        add_field(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as payload:
            for chunk in iter(lambda: payload.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    if not path.is_dir():
        raise ValueError(f"baseline payload must be a regular file or directory: {path}")

    add_field(b"directory")
    entries: list[Path] = []
    for current, directories, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        entries.extend(current_path / name for name in directories)
        entries.extend(current_path / name for name in files)

    for entry in sorted(entries, key=lambda item: item.relative_to(path).as_posix()):
        add_field(entry.relative_to(path).as_posix().encode("utf-8"))
        if entry.is_symlink():
            add_field(b"symlink")
            add_field(os.readlink(entry).encode("utf-8"))
        elif entry.is_dir():
            add_field(b"directory")
        elif entry.is_file():
            add_field(b"file")
            add_field(entry.stat().st_size.to_bytes(8, "big"))
            with entry.open("rb") as payload:
                for chunk in iter(lambda: payload.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            raise ValueError(f"unsupported baseline payload entry: {entry}")
    return digest.hexdigest()


def promote_to_baseline(
    source: str | Path,
    destination: str | Path,
    manifest: ArtifactManifest,
    *,
    validate: Validator,
) -> Path:
    """Validate and atomically publish an artifact as a baseline directory.

    ``destination`` contains the copied source under ``payload`` and a
    completion/provenance record under ``manifest.json``. The validator checks
    the staged payload, and publication happens only after validation succeeds.
    """
    if manifest.retention is not RetentionClass.BASELINE_PROMOTABLE:
        raise ValueError("artifact is not baseline-promotable")
    if not manifest.parents:
        raise ValueError("baseline promotion requires a parent artifact identity")
    source_revision = manifest.provenance.get("source_revision")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise ValueError("baseline promotion requires provenance.source_revision")
    src, dst = Path(source).resolve(), Path(destination).resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    if not src.is_file() and not src.is_dir():
        raise ValueError(f"baseline source must be a regular file or directory: {src}")
    if dst.exists():
        raise FileExistsError(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{dst.name}.", dir=dst.parent) as temp_dir:
        staging = Path(temp_dir) / "promotion"
        staging.mkdir()
        payload = staging / "payload"
        if src.is_dir():
            shutil.copytree(src, payload, symlinks=True)
        else:
            shutil.copy2(src, payload)

            # Validate the staged copy that will actually be published. This keeps
            # a concurrent source update from changing the baseline after approval.
        payload_sha256 = _payload_sha256(payload)
        validation = validate(payload)
        if not isinstance(validation, BaselineValidation):
            raise TypeError("baseline validator must return BaselineValidation")
        if _payload_sha256(payload) != payload_sha256:
            raise ValueError("baseline validator modified the staged payload")
        promotion = {
            "source": str(src),
            "payload_sha256": payload_sha256,
            "validator": f"{validate.__module__}.{validate.__qualname__}",
            "validation": validation.to_dict(),
        }
        promoted_manifest = replace(
            manifest,
            provenance={**manifest.provenance, "promotion": promotion},
        )
        write_json_atomic(staging / "manifest.json", promoted_manifest.to_dict())
        staging.rename(dst)
    return dst
