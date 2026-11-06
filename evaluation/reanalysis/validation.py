"""Input, schema, and provenance checks for deterministic reanalysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from artifacts.identity import file_sha256
from evaluation.reporting.run_manifest import build_sequence_feature_schema


def validate_train_only_feature_snapshot_request(
    *,
    train_only_screen: bool,
    source_feature_cache: str | None,
    train_only_feature_snapshot: str | None,
) -> None:
    """Restrict reconstructed feature snapshots to a train-only replay.

    Args:
        train_only_screen: Whether only the training split is requested.
        source_feature_cache: Exact all-period source cache, if requested.
        train_only_feature_snapshot: Assembled train-only feature frame, if requested.
    """
    if train_only_feature_snapshot is None:
        return
    if not train_only_screen:
        raise ValueError("--train-only-feature-snapshot requires --train-only-screen")
    if source_feature_cache is not None:
        raise ValueError(
            "--train-only-feature-snapshot cannot be combined with --source-feature-cache"
        )


def resolve_execution_seed(
    requested_seed: int | None, source_manifest: dict[str, Any]
) -> int | None:
    """Use an explicit replay seed or the recorded training seed for fill jitter.

    Args:
        requested_seed: Requested seed used by the operation described above.
        source_manifest: Key-value data used for the source manifest.

    Returns:
        Result of use an explicit replay seed or the recorded training seed for fill jitter.
    """
    if requested_seed is not None:
        if requested_seed < 0:
            raise ValueError("evaluation seed must be non-negative")
        return requested_seed
    training_protocol = source_manifest.get("training_protocol")
    metrics_protocol = source_manifest.get("metrics_protocol")
    candidates = (
        source_manifest.get("seed"),
        training_protocol.get("seed") if isinstance(training_protocol, dict) else None,
        metrics_protocol.get("execution_seed") if isinstance(metrics_protocol, dict) else None,
    )
    for candidate in candidates:
        if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 0:
            return candidate
    return None


def validate_sequence_input_width(model: Any, expected_width: int) -> int:
    """Require the checkpoint's sequence tensor width to match its feature schema.

    Args:
        model: Model used for this operation.
        expected_width: Number specifying the expected width for this operation.

    Returns:
        Numeric result returned by ``validate_sequence_input_width``.
    """
    observation_spaces = getattr(getattr(model, "observation_space", None), "spaces", None)
    get_space = getattr(observation_spaces, "get", None)
    sequence_space = get_space("seq") if callable(get_space) else None
    shape = getattr(sequence_space, "shape", None)
    if not shape or int(shape[-1]) != int(expected_width):
        raise ValueError(
            "checkpoint sequence input width disagrees with evaluated feature coordinates: "
            f"checkpoint={shape}, expected={expected_width}"
        )
    return int(shape[-1])


def resolve_recorded_sequence_schema(
    schema: dict[str, Any] | None,
    *,
    available_columns: set[str],
    generated_columns: set[str],
    train_only_screen: bool,
    has_train_only_feature_snapshot: bool,
    mtf_enabled: bool,
    feature_validity_channels: bool,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Validate and return exact saved sequence coordinates for a train-only replay.

    This opt-in is for reproducing an existing checkpoint's recorded input
    layout. It requires a hashed training-only feature snapshot and does not
    permit MTF observation branches, whose coordinates are a separate contract.

    Args:
        schema: Saved sequence-feature schema from the checkpoint manifest.
        available_columns: Feature columns already present in the replay frame.
        generated_columns: Columns that replay can deterministically construct.
        train_only_screen: Whether this replay is restricted to training data.
        has_train_only_feature_snapshot: Whether a hashed training snapshot exists.
        mtf_enabled: Whether the policy uses separate timeframe observations.
        feature_validity_channels: Whether validity-mask channels are configured.

    Returns:
        Validated schema and its ordered sequence feature columns.
    """
    if not train_only_screen:
        raise ValueError("recorded sequence schema replay requires --train-only-screen")
    if not has_train_only_feature_snapshot:
        raise ValueError("recorded sequence schema replay requires --train-only-feature-snapshot")
    if mtf_enabled:
        raise ValueError(
            "recorded sequence schema replay does not support MTF observation branches"
        )
    if not isinstance(schema, dict):
        raise ValueError("recorded sequence schema replay requires a saved sequence schema")
    columns = schema.get("columns")
    if (
        not isinstance(columns, list)
        or not columns
        or any(not isinstance(column, str) or not column for column in columns)
        or len(columns) != len(set(columns))
    ):
        raise ValueError("saved sequence schema must contain unique ordered column names")
    version = schema.get("version")
    include_validity_channels = version == "sequence-feature-validity-channels-v1"
    if version not in {"sequence-feature-columns-v1", "sequence-feature-validity-channels-v1"}:
        raise ValueError("saved sequence schema version is unsupported for recorded replay")
    if include_validity_channels != feature_validity_channels:
        raise ValueError("saved sequence schema validity channels differ from the run config")
    rebuilt = build_sequence_feature_schema(
        columns,
        include_validity_channels=include_validity_channels,
    )
    if rebuilt != schema:
        raise ValueError("saved sequence schema hash or dimensions are inconsistent")
    missing = set(columns) - available_columns - generated_columns
    if missing:
        raise ValueError(
            "saved sequence schema columns are absent from the training feature frame: "
            f"{sorted(missing)[:10]}"
        )
    return rebuilt, tuple(columns)


def validate_stop_candidate_schema(
    *,
    checkpoint_schema: dict[str, Any] | None,
    manifest_schema: dict[str, Any] | None,
    expected_schema: dict[str, Any],
    allow_legacy: bool,
    allow_changed_menu: bool = False,
) -> str:
    """Reject checkpoint/config drift and label explicit latest-swing legacy use.

    Args:
        checkpoint_schema: Key-value data used for the checkpoint schema.
        manifest_schema: Key-value data used for the manifest schema.
        expected_schema: Key-value data used for the expected schema.
        allow_legacy: Whether to enable or require the allow legacy.
        allow_changed_menu: Whether this is an explicitly labelled changed-policy diagnostic.

    Returns:
        Text returned by ``validate_stop_candidate_schema``.
    """
    if checkpoint_schema is None or manifest_schema is None:
        if not allow_legacy:
            raise ValueError(
                "checkpoint or run manifest has no stop-candidate schema; pass "
                "--allow-legacy-stop-schema only when intentionally reanalysing a legacy run"
            )
        available_schema = checkpoint_schema if checkpoint_schema is not None else manifest_schema
        if available_schema is None:
            if expected_schema.get("menu") != "legacy_last_accepted_swing_v1":
                raise ValueError(
                    "legacy checkpoint has no stop schema and the run config requests the "
                    "expanded multi-timeframe menu; legacy opt-in cannot assert that menu "
                    "was trained"
                )
        elif available_schema != expected_schema:
            raise ValueError(
                "available stop-candidate schema differs from the run config; legacy opt-in "
                "does not authorize evaluating under a changed stop menu"
            )
        return "legacy_opt_in"
    if checkpoint_schema != manifest_schema:
        raise ValueError("checkpoint and run manifest stop-candidate schemas disagree")
    if checkpoint_schema != expected_schema:
        if allow_changed_menu:
            return "changed_policy_diagnostic"
        raise ValueError(
            "checkpoint stop-candidate schema differs from the run config; refusing to evaluate "
            "under a changed stop menu"
        )
    return "versioned"


def validate_checkpoint_manifest_hash(path: Path, manifest: dict[str, Any]) -> str:
    """Verify the checkpoint is the exact artifact recorded by its run manifest.

    Args:
        path: Path to the input file or directory.
        manifest: Key-value data used for the manifest.

    Returns:
        Text returned by ``validate_checkpoint_manifest_hash``.
    """
    checkpoint_record = manifest.get("checkpoint")
    expected_hash = checkpoint_record.get("sha256") if isinstance(checkpoint_record, dict) else None
    if expected_hash is None:
        return "unavailable_legacy_manifest"
    actual_hash = file_sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(
            "checkpoint SHA-256 does not match the source run manifest; refusing reanalysis"
        )
    return "verified"


__all__ = [
    "resolve_execution_seed",
    "validate_train_only_feature_snapshot_request",
    "validate_checkpoint_manifest_hash",
    "validate_sequence_input_width",
    "resolve_recorded_sequence_schema",
    "validate_stop_candidate_schema",
]
