"""Audit the registered research-question and configuration inventory."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from research_tools.studies.study_plan import build_study_plan


def audit_registered_configs(
    root: Path, study: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    """Return the resolved question/config inventory without launching studies."""
    del study, output_dir
    plan = build_study_plan(root)
    type_counts = Counter(item["type"] for module in plan["modules"] for item in module["studies"])
    rows = [
        {
            "module_id": module["id"],
            "study_id": item["id"],
            "type": item["type"],
            "enabled": item["enabled"],
            "source_paths": item["source_paths"],
            "config_paths": item["config_paths"],
            "effective_inputs_sha256": item["effective_inputs_sha256"],
        }
        for module in plan["modules"]
        for item in module["studies"]
    ]
    return {
        "diagnostic_status": "validated",
        "module_count": len(plan["modules"]),
        "study_count": len(rows),
        "study_type_counts": dict(sorted(type_counts.items())),
        "empirical_studies_registered_not_run": [
            row["study_id"] for row in rows if row["type"] == "empirical"
        ],
        "disposition_rows": rows,
    }
