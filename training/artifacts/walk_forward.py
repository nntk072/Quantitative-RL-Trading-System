"""Identity helpers for resumable walk-forward evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from artifacts.atomic import write_text_atomic


def _file_sha256(path: Path) -> str:
    """Hash a file's exact bytes with SHA-256.

    Args:
        path: File whose bytes will be hashed.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
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
    """Bind persisted folds to their immutable seed run and exact protocol.

    Args:
        run_manifest_path: Manifest for the completed seed run.
        seed: Random seed used for the run.
        wf_splits: Number of configured walk-forward folds.
        purge_bars: Purge interval between training and test data.
        embargo_bars: Embargo interval before each test fold.
        wf_steps: Training steps used for each fold.

    Returns:
        Stable identity fields used to validate resumed progress.
    """
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
    """Hash ordered train/test row positions for one purged fold.

    Args:
        train_indices: Ordered row positions assigned to fold training.
        test_indices: Ordered row positions assigned to fold testing.

    Returns:
        SHA-256 digest of both ordered index arrays.
    """
    digest = hashlib.sha256()
    for values in (train_indices, test_indices):
        array = np.asarray(values, dtype="<i8")
        digest.update(len(array).to_bytes(8, "big"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def fold_identity_sha256(identity: dict[str, Any], fold: int, split_sha256: str) -> str:
    """Return the stable identity for one fold within a qualified seed run.

    Args:
        identity: Seed and protocol identity shared by the campaign.
        fold: Fold identifier.
        split_sha256: Digest of the fold's train/test row positions.

    Returns:
        SHA-256 digest binding the run identity to this fold split.
    """
    payload = json.dumps(
        {"identity": identity, "fold": int(fold), "split_sha256": split_sha256},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _walk_forward_fold_receipt_path(receipts_dir: Path, fold: int) -> Path:
    """Return the immutable receipt path for one completed fold.

    Args:
        receipts_dir: Directory storing immutable fold receipts.
        fold: Fold identifier.

    Returns:
        Path assigned to the fold receipt.
    """
    return receipts_dir / f"fold_{int(fold)}.json"


def _write_walk_forward_fold_receipt(
    receipts_dir: Path, *, identity: dict[str, Any], record: dict[str, Any]
) -> Path:
    """Persist a fold result once so later aggregate updates cannot rewrite it.

    Args:
        receipts_dir: Directory storing immutable fold receipts.
        identity: Seed and protocol identity shared by the campaign.
        record: Completed fold result to persist.

    Returns:
        Path to the validated or newly written receipt.
    """
    fold = record.get("fold")
    if isinstance(fold, bool) or not isinstance(fold, int):
        raise ValueError("walk-forward receipt requires an integer fold ID")
    path = _walk_forward_fold_receipt_path(receipts_dir, fold)
    payload = {
        "schema_version": "walk-forward-fold-receipt-v1",
        "identity": identity,
        "record": record,
    }
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read walk-forward fold receipt: {path}") from exc
        if existing != payload:
            raise ValueError(f"walk-forward fold {fold} receipt differs from its result")
        return path
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True))
    return path


def load_walk_forward_progress(
    path: Path,
    *,
    identity: dict[str, Any],
    expected_fold_ids: set[int],
    receipts_dir: Path | None = None,
) -> dict[int, dict[str, Any]]:
    """Load and validate persisted fold progress and immutable receipts.

    Args:
        path: Mutable aggregate progress file.
        identity: Seed and protocol identity expected in persisted records.
        expected_fold_ids: Configured fold IDs allowed by the split contract.
        receipts_dir: Optional directory holding immutable per-fold records.

    Returns:
        Validated fold records keyed by fold ID.
    """
    previous: dict[int, dict[str, Any]] = {}
    if path.is_file():
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
        for record in records:
            if not isinstance(record, dict) or isinstance(record.get("fold"), bool):
                raise ValueError("walk-forward progress contains a malformed fold record")
            fold_id = record.get("fold")
            if not isinstance(fold_id, int):
                raise ValueError("walk-forward progress contains a malformed fold record")
            split_sha = str(record.get("split_sha256", ""))
            if fold_id not in expected_fold_ids or fold_id in previous:
                raise ValueError("walk-forward progress contains an unexpected or duplicate fold")
            if record.get("fold_identity_sha256") != fold_identity_sha256(
                identity, fold_id, split_sha
            ):
                raise ValueError(f"walk-forward fold {fold_id} identity is invalid")
            previous[fold_id] = record
        is_complete = set(previous) == expected_fold_ids
        if (payload["status"] == "complete") != is_complete:
            raise ValueError("walk-forward completion status disagrees with its fold records")

    if receipts_dir is not None:
        if not receipts_dir.exists() and previous:
            raise ValueError("walk-forward fold receipts are missing for persisted progress")
        if receipts_dir.exists() and not receipts_dir.is_dir():
            raise ValueError(f"walk-forward receipt path is not a directory: {receipts_dir}")
        receipts: dict[int, dict[str, Any]] = {}
        for receipt_path in (
            sorted(receipts_dir.glob("fold_*.json")) if receipts_dir.is_dir() else []
        ):
            try:
                fold_id = int(receipt_path.stem.removeprefix("fold_"))
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"cannot resume malformed walk-forward receipt: {receipt_path}"
                ) from exc
            if (
                fold_id not in expected_fold_ids
                or receipt_path != _walk_forward_fold_receipt_path(receipts_dir, fold_id)
                or not isinstance(receipt, dict)
                or receipt.get("schema_version") != "walk-forward-fold-receipt-v1"
                or receipt.get("identity") != identity
                or not isinstance(receipt.get("record"), dict)
                or receipt["record"].get("fold") != fold_id
                or fold_id in receipts
            ):
                raise ValueError(
                    "walk-forward receipt identity differs from the seed run or protocol"
                )
            record = receipt["record"]
            split_sha = str(record.get("split_sha256", ""))
            if record.get("fold_identity_sha256") != fold_identity_sha256(
                identity, fold_id, split_sha
            ):
                raise ValueError(f"walk-forward receipt {fold_id} identity is invalid")
            receipts[fold_id] = record
        for fold_id, record in previous.items():
            if receipts.get(fold_id) != record:
                raise ValueError(f"walk-forward fold {fold_id} receipt is missing or changed")
        previous.update(
            {fold_id: record for fold_id, record in receipts.items() if fold_id not in previous}
        )
    return previous


def build_walk_forward_progress(
    *,
    identity: dict[str, Any],
    expected_fold_ids: set[int],
    purge_bars: int,
    embargo_bars: int,
    folds: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Build the atomic progress payload after one fold is durably completed.

    Args:
        identity: Seed and protocol identity shared by the campaign.
        expected_fold_ids: Fold IDs required for complete status.
        purge_bars: Purge interval used for the split protocol.
        embargo_bars: Embargo interval used for the split protocol.
        folds: Completed fold records keyed by fold ID.

    Returns:
        Aggregate progress payload ready for atomic persistence.
    """
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
