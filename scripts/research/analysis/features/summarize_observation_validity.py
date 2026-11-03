"""Summarize profile-wide feature validity into reviewable triage priorities.

The report describes observed missingness patterns. It does not infer why a
feature is missing or whether a finite zero is economically meaningful.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path(
    "evidence/research/feature_causality/observation_validity_across_profiles/"
    "column_warmup_all_profiles.csv"
)
DEFAULT_OUTPUT = Path("evidence/research/feature_causality/observation_validity_priorities")
REQUIRED_COLUMNS = {
    "profile_group",
    "profile_ids",
    "timeframe",
    "feature",
    "sampled_rows",
    "finite_rows",
    "nonfinite_rows",
    "leading_nonfinite_rows",
    "interior_nonfinite_rows",
    "finite_zero_rows",
    "missing_collides_with_finite_zero",
}


def _parse_bool(value: str, *, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{field} must be true or false, got {value!r}")
    return normalized == "true"


def _parse_row(row: dict[str, str], *, row_number: int) -> dict[str, Any]:
    parsed: dict[str, Any] = dict(row)
    for column in (
        "sampled_rows",
        "finite_rows",
        "nonfinite_rows",
        "leading_nonfinite_rows",
        "interior_nonfinite_rows",
        "finite_zero_rows",
    ):
        try:
            parsed[column] = int(row[column])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"row {row_number}: {column} must be a non-negative integer") from exc
        if parsed[column] < 0:
            raise ValueError(f"row {row_number}: {column} cannot be negative")

    try:
        profile_ids = json.loads(row["profile_ids"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f"row {row_number}: profile_ids must be a JSON list") from exc
    if not isinstance(profile_ids, list) or not all(
        isinstance(profile_id, str) and profile_id for profile_id in profile_ids
    ):
        raise ValueError(f"row {row_number}: profile_ids must contain strings")
    parsed["profile_ids"] = profile_ids
    parsed["missing_collides_with_finite_zero"] = _parse_bool(
        row.get("missing_collides_with_finite_zero", ""),
        field="missing_collides_with_finite_zero",
    )

    if parsed["finite_rows"] + parsed["nonfinite_rows"] != parsed["sampled_rows"]:
        raise ValueError(f"row {row_number}: finite/non-finite counts do not sum")
    if (
        parsed["leading_nonfinite_rows"] + parsed["interior_nonfinite_rows"]
        != parsed["nonfinite_rows"]
    ):
        raise ValueError(f"row {row_number}: leading/interior counts do not sum")
    if parsed["finite_zero_rows"] > parsed["finite_rows"]:
        raise ValueError(f"row {row_number}: finite-zero count exceeds finite rows")
    if not all(row.get(column, "").strip() for column in ("profile_group", "timeframe", "feature")):
        raise ValueError(f"row {row_number}: group, timeframe, and feature are required")
    return parsed


def summarize_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Aggregate one observation-validity row per profile-group/feature key."""
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    seen: set[tuple[str, str, str]] = set()
    for row_number, raw in enumerate(rows, start=2):
        row = _parse_row(raw, row_number=row_number)
        group_key = (row["profile_group"], row["timeframe"], row["feature"])
        if group_key in seen:
            raise ValueError(f"row {row_number}: duplicate profile-group feature key")
        seen.add(group_key)

        key = (row["timeframe"], row["feature"])
        aggregate = aggregates.setdefault(
            key,
            {
                "timeframe": row["timeframe"],
                "feature": row["feature"],
                "profile_group_count": 0,
                "profile_ids": set(),
                "sampled_rows": 0,
                "finite_rows": 0,
                "nonfinite_rows": 0,
                "leading_nonfinite_rows": 0,
                "interior_nonfinite_rows": 0,
                "finite_zero_rows": 0,
                "fully_nonfinite_group_count": 0,
                "interior_missing_group_count": 0,
                "finite_zero_collision_group_count": 0,
                "groups_with_missing_values": 0,
            },
        )
        aggregate["profile_group_count"] += 1
        aggregate["profile_ids"].update(row["profile_ids"])
        for column in (
            "sampled_rows",
            "finite_rows",
            "nonfinite_rows",
            "leading_nonfinite_rows",
            "interior_nonfinite_rows",
            "finite_zero_rows",
        ):
            aggregate[column] += row[column]
        aggregate["fully_nonfinite_group_count"] += int(
            row["sampled_rows"] > 0 and row["nonfinite_rows"] == row["sampled_rows"]
        )
        aggregate["interior_missing_group_count"] += int(row["interior_nonfinite_rows"] > 0)
        aggregate["finite_zero_collision_group_count"] += int(
            row["missing_collides_with_finite_zero"]
        )
        aggregate["groups_with_missing_values"] += int(row["nonfinite_rows"] > 0)

    result: list[dict[str, Any]] = []
    for aggregate in aggregates.values():
        profile_ids = aggregate.pop("profile_ids")
        aggregate["profile_count"] = len(profile_ids)
        sampled = aggregate["sampled_rows"]
        aggregate["nonfinite_fraction"] = aggregate["nonfinite_rows"] / sampled if sampled else 0.0
        flags: list[str] = []
        if aggregate["nonfinite_rows"] == 0:
            flags.append("no_nonfinite_values")
        else:
            if aggregate["fully_nonfinite_group_count"] == aggregate["profile_group_count"]:
                flags.append("fully_nonfinite_in_every_group")
            elif aggregate["fully_nonfinite_group_count"]:
                flags.append("fully_nonfinite_in_some_groups")
            if aggregate["interior_nonfinite_rows"]:
                flags.append("interior_missing_values_present")
            elif aggregate["leading_nonfinite_rows"]:
                flags.append("missing_values_only_at_leading_edge")
            if aggregate["groups_with_missing_values"] < aggregate["profile_group_count"]:
                flags.append("missingness_varies_across_groups")
        if aggregate["finite_zero_collision_group_count"]:
            flags.append("missing_collides_with_finite_zero")
        aggregate["triage_flags"] = flags
        result.append(aggregate)

    return sorted(
        result,
        key=lambda row: (
            -int("fully_nonfinite_in_every_group" in row["triage_flags"]),
            -int("interior_missing_values_present" in row["triage_flags"]),
            -int("missing_collides_with_finite_zero" in row["triage_flags"]),
            -row["nonfinite_fraction"],
            row["timeframe"],
            row["feature"],
        ),
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def build_report(input_path: Path, output_dir: Path) -> dict[str, Any]:
    input_bytes = input_path.read_bytes()
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    with io.StringIO(input_bytes.decode("utf-8"), newline="") as stream:
        reader = csv.DictReader(stream)
        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing_columns:
            raise ValueError(f"input is missing columns: {sorted(missing_columns)}")
        summaries = summarize_rows(list(reader))
    source_path = Path(__file__).resolve()
    report: dict[str, Any] = {
        "schema": "qrl.observation_validity_priorities.v1",
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "input_path": str(input_path.resolve()),
        "input_sha256": input_sha256,
        "analyzer_path": str(source_path),
        "analyzer_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "feature_timeframe_count": len(summaries),
        "profile_group_count": len(
            {
                row["profile_group"]
                for row in csv.DictReader(io.StringIO(input_bytes.decode("utf-8")))
            }
        ),
        "all_groups_fully_nonfinite_count": sum(
            "fully_nonfinite_in_every_group" in row["triage_flags"] for row in summaries
        ),
        "interior_missing_count": sum(
            "interior_missing_values_present" in row["triage_flags"] for row in summaries
        ),
        "finite_zero_collision_count": sum(
            "missing_collides_with_finite_zero" in row["triage_flags"] for row in summaries
        ),
        "summaries": summaries,
        "interpretation_limit": (
            "Triage flags describe observed counts only; producer semantics and "
            "economic meaning require separate source review."
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "feature_validity_priorities.csv"
    json_path = output_dir / "feature_validity_priorities.json"
    readme_path = output_dir / "README.md"
    checksum_path = output_dir / "SHA256SUMS"
    csv_fields = [
        "timeframe",
        "feature",
        "profile_group_count",
        "profile_count",
        "sampled_rows",
        "finite_rows",
        "nonfinite_rows",
        "nonfinite_fraction",
        "leading_nonfinite_rows",
        "interior_nonfinite_rows",
        "finite_zero_rows",
        "fully_nonfinite_group_count",
        "interior_missing_group_count",
        "finite_zero_collision_group_count",
        "groups_with_missing_values",
        "triage_flags",
    ]
    csv_stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        csv_stream, fieldnames=csv_fields, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in summaries:
        csv_row = dict(row)
        csv_row["triage_flags"] = ";".join(row["triage_flags"])
        writer.writerow(csv_row)
    csv_bytes = csv_stream.getvalue().encode("utf-8")
    json_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    command = (
        ".venv/bin/python scripts/research/analysis/features/summarize_observation_validity.py"
    )
    if input_path.resolve() != DEFAULT_INPUT.resolve():
        command += f" --input {input_path.resolve()}"
    if output_dir.resolve() != DEFAULT_OUTPUT.resolve():
        command += f" --output-dir {output_dir.resolve()}"
    readme = (
        "# Observation validity priorities\n\n"
        "This packet aggregates the profile-wide observation-validity table by "
        "timeframe and feature. Flags identify all-group missingness, interior "
        "missing values, cross-group differences, and missing/finite-zero "
        "collisions. They are triage signals only; they do not establish the "
        "producer-level cause or economic meaning.\n\n"
        f"Input SHA-256: `{input_sha256}`. Analyzer SHA-256: "
        f"`{report['analyzer_sha256']}`.\n\n"
        "Regenerate with:\n\n```bash\n"
        f"{command}\n```.\n"
    ).encode()

    _atomic_write(csv_path, csv_bytes)
    _atomic_write(json_path, json_bytes)
    _atomic_write(readme_path, readme)
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (csv_path, json_path, readme_path)
    ).encode("utf-8")
    _atomic_write(checksum_path, checksums)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(args.input, args.output_dir)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "feature_timeframe_count",
                    "profile_group_count",
                    "all_groups_fully_nonfinite_count",
                    "interior_missing_count",
                    "finite_zero_collision_count",
                )
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
