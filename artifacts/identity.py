from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactId:
    """Stable content identity for one artifact and its semantic inputs.

    Attributes:
        kind: Artifact category used to namespace the digest.
        digest: SHA-256 hex digest of canonical semantic inputs.
    """

    kind: str
    digest: str

    def __str__(self) -> str:
        """Process ArtifactId.

        Returns:
            Text returned by ``__str__``.
        """
        return f"{self.kind}:{self.digest}"


def artifact_id(kind: str, semantic_inputs: Any) -> ArtifactId:
    """Create a deterministic artifact identity from its kind and semantic inputs.

    Args:
        kind: Namespace identifying the artifact type.
        semantic_inputs: JSON-compatible values that determine artifact contents.

    Returns:
        Identity containing the kind and canonical SHA-256 digest.
    """
    payload = json.dumps(
        semantic_inputs, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return ArtifactId(kind, hashlib.sha256(payload).hexdigest())


def file_sha256(path: str | Path) -> str:
    """Hash file contents in bounded memory for artifact provenance.

    Args:
        path: Path to the input file or directory.

    Returns:
        Text returned by ``file_sha256``.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
