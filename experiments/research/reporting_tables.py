"""Reporting tables generated from consolidated research results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _object(path: Path) -> dict[str, Any]:
    """Load one JSON object from disk.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def build_research_tables(results_path: Path, output_dir: Path) -> dict[str, Any]:
    """Write compact domain/experiment summaries without inventing missing outcomes.

    Args:
        results_path: Path to consolidated research results.
        output_dir: Directory that receives generated artifacts.

    Returns:
        Result produced by build_research_tables.
    """
    results = _object(results_path)
    rows = results.get("results")
    if results.get("schema_version") != 1 or not isinstance(rows, list):
        raise ValueError("unsupported consolidated research results")
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("domain", "")),
            str(row.get("experiment", "")),
            str(row.get("component") or row.get("domain") or ""),
            str(row.get("variant", "")),
        )
        item = summary.setdefault(
            key,
            {
                "domain": key[0],
                "experiment": key[1],
                "component": key[2],
                "variant": key[3],
                "records": 0,
                "passed": 0,
                "failed": 0,
                "other": 0,
            },
        )
        item["records"] += 1
        status = str(row.get("status", ""))
        if status in {"pass", "passed", "positive"}:
            item["passed"] += 1
        elif status in {"fail", "failed", "negative_or_inconclusive"}:
            item["failed"] += 1
        else:
            item["other"] += 1
    table_rows = [summary[key] for key in sorted(summary)]
    csv_path = output_dir / "research_result_inventory.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "domain",
                "experiment",
                "component",
                "variant",
                "records",
                "passed",
                "failed",
                "other",
            ],
        )
        writer.writeheader()
        writer.writerows(table_rows)
    markdown = [
        "# Research result inventory",
        "",
        "| Domain | Experiment | Component | Variant | Records | Passed | Failed/inconclusive | Other |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in table_rows:
        markdown.append(
            f"| {row['domain']} | {row['experiment']} | {row['component']} | "
            f"{row['variant']} | "
            f"{row['records']} | {row['passed']} | {row['failed']} | {row['other']} |"
        )
    markdown.append("")
    markdown.append(
        "This inventory reports only generated evidence. Missing execution-dependent outcomes "
        "remain absent rather than being replaced with placeholders or historical superseded results."
    )
    markdown_path = output_dir / "research_result_inventory.md"
    markdown_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "row_count": len(table_rows),
        "csv": str(csv_path),
        "markdown": str(markdown_path),
    }


__all__ = ["build_research_tables"]
