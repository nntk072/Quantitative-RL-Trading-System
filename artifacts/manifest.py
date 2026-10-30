from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .retention import RetentionClass


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    kind: str
    artifact_id: str
    schema_version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    retention: RetentionClass = RetentionClass.RUN_RETAINED
    parents: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("artifact manifest kind must be non-empty")
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ValueError("artifact manifest id must be non-empty")
        if type(self.schema_version) is not int or self.schema_version < 1:
            raise ValueError("artifact manifest schema_version must be a positive integer")
        if not isinstance(self.created_at, str) or not self.created_at.strip():
            raise ValueError("artifact manifest created_at must be non-empty")
        if not isinstance(self.retention, RetentionClass):
            raise ValueError("artifact manifest retention must be a RetentionClass")
        if not isinstance(self.parents, tuple):
            raise ValueError("artifact manifest parents must be a tuple of artifact ids")
        if any(not isinstance(parent, str) or not parent.strip() for parent in self.parents):
            raise ValueError("artifact manifest parents must be non-empty artifact ids")
        if not isinstance(self.provenance, dict):
            raise ValueError("artifact manifest provenance must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["retention"] = str(self.retention)
        return result

    @classmethod
    def read(cls, path: str | Path) -> ArtifactManifest:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError("artifact manifest root must be a mapping")
        try:
            data = dict(data)
            data["retention"] = RetentionClass(data.get("retention", RetentionClass.RUN_RETAINED))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"artifact manifest has invalid retention: {exc}") from exc
        parents = data.get("parents", ())
        if not isinstance(parents, (list, tuple)):
            raise ValueError("artifact manifest parents must be a sequence of artifact ids")
        data["parents"] = tuple(parents)
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError(f"artifact manifest fields are invalid: {exc}") from exc
