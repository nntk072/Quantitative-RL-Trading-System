"""Identity helpers for resumable walk-forward evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_walk_forward_identity(
    *,
    run_manifest_path: Path,
    seed: int,
    wf_splits: int,
    purge_bars: int,
    embargo_bars: int,
    wf_steps: int,
) -> dict[str, Any]:
    """Bind persisted folds to their immutable seed run and exact protocol."""
    return {
        "schema_version": "walk-forward-progress-v1",
        "seed": int(seed),
        "run_manifest_sha256": _file_sha256(run_manifest_path),
        "wf_splits": int(wf_splits),
        "purge_bars": int(purge_bars),
        "embargo_bars": int(embargo_bars),
        "wf_steps": int(wf_steps),
    }


def fold_split_sha256(train_indices: Any, test_indices: Any) -> str:
    """Hash ordered train/test row positions for one purged fold."""
    digest = hashlib.sha256()
    for values in (train_indices, test_indices):
        array = np.asarray(values, dtype="<i8")
        digest.update(len(array).to_bytes(8, "big"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def fold_identity_sha256(identity: dict[str, Any], fold: int, split_sha256: str) -> str:
    """Return the stable identity for one fold within a qualified seed run."""
    payload = json.dumps(
        {"identity": identity, "fold": int(fold), "split_sha256": split_sha256},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_walk_forward_progress(
    path: Path, *, identity: dict[str, Any], expected_fold_ids: set[int]
) -> dict[int, dict[str, Any]]:
    """Load only progress records that match the seed run and exact fold set."""
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot resume malformed walk-forward progress: {path}") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "walk-forward-progress-v1"
        or payload.get("identity") != identity
        or payload.get("status") not in {"incomplete", "complete"}
    ):
        raise ValueError("walk-forward progress identity differs from the seed run or protocol")
    records = payload.get("folds")
    if not isinstance(records, list):
        raise ValueError("walk-forward progress must contain a fold list")
    previous: dict[int, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("fold"), int):
            raise ValueError("walk-forward progress contains a malformed fold record")
        fold_id = int(record["fold"])
        split_sha = str(record.get("split_sha256", ""))
        if fold_id not in expected_fold_ids or fold_id in previous:
            raise ValueError("walk-forward progress contains an unexpected or duplicate fold")
        if record.get("fold_identity_sha256") != fold_identity_sha256(identity, fold_id, split_sha):
            raise ValueError(f"walk-forward fold {fold_id} identity is invalid")
        previous[fold_id] = record
    is_complete = set(previous) == expected_fold_ids
    if (payload["status"] == "complete") != is_complete:
        raise ValueError("walk-forward completion status disagrees with its fold records")
    return previous


def build_walk_forward_progress(
    *,
    identity: dict[str, Any],
    expected_fold_ids: set[int],
    purge_bars: int,
    embargo_bars: int,
    folds: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Build the atomic progress payload after one fold is durably completed."""
    ordered = [folds[index] for index in sorted(folds)]
    sharpes = [float(record["sharpe"]) for record in ordered]
    return {
        "schema_version": "walk-forward-progress-v1",
        "identity": identity,
        "status": "complete" if set(folds) == expected_fold_ids else "incomplete",
        "splits": len(expected_fold_ids),
        "purge_bars": int(purge_bars),
        "embargo_bars": int(embargo_bars),
        "wf_steps": int(identity["wf_steps"]),
        "folds": ordered,
        "mean_sharpe": float(np.mean(sharpes)) if sharpes else None,
        "std_sharpe": float(np.std(sharpes)) if sharpes else None,
    }
