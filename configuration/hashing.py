from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonical_config_bytes(config: Mapping[str, Any]) -> bytes:
    """Serialize configuration values with deterministic key ordering.

    Args:
        config: Configuration mapping to encode.

    Returns:
        UTF-8 bytes for the canonical JSON representation.
    """
    return json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")


def config_sha256(config: Mapping[str, Any]) -> str:
    """Hash the canonical representation of a configuration mapping.

    Args:
        config: Configuration values to serialize deterministically.

    Returns:
        Lowercase SHA-256 hex digest.
    """
    return hashlib.sha256(canonical_config_bytes(config)).hexdigest()
