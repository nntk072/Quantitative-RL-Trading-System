"""Render typed metric data without recalculating scientific measures."""

from __future__ import annotations

import json

from evaluation.contracts import ReportDataset


def render_json(report: ReportDataset) -> str:
    """Serialize the already-computed report dataset as JSON.

    Args:
        report: Report used by the operation described above.

    Returns:
        Text returned by ``render_json``.
    """
    payload = {
        "case_id": report.case.case_id,
        "dataset_id": report.case.dataset.dataset_id,
        "metrics": [
            {"name": metric.name, "value": metric.value, "unit": metric.unit}
            for metric in report.metrics
        ],
    }
    return json.dumps(payload, sort_keys=True)


def render_markdown_table(report: ReportDataset) -> str:
    """Render the already-computed report dataset as a compact Markdown table.

    Args:
        report: Report used by the operation described above.

    Returns:
        Text returned by ``render_markdown_table``.
    """
    rows = ["| Metric | Value | Unit |", "|---|---:|---|"]
    rows.extend(
        f"| {metric.name} | {metric.value:g} | {metric.unit} |" for metric in report.metrics
    )
    return "\n".join(rows)


__all__ = ["render_json", "render_markdown_table"]
