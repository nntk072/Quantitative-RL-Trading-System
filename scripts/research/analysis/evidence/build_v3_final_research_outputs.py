#!/usr/bin/env python3
"""Generate the final V3 research/report result package from verified canonical inputs.

The input manifest contains measured rows and source-artifact identities. This
tool does not invent metrics and refuses source files whose bytes changed.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf
from scripts.research.audits.record_pretraining_scientific_gate import file_sha256

from artifacts.atomic import write_json_atomic
from configuration.paths import repository_root

ROOT = repository_root(__file__)
DEFAULT_CONTRACT = ROOT / "config/research/v3_final_output_contract.yaml"


def _verify_sources(rows: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{label} requires at least one source artifact")
    verified = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} source artifact must be an object")
        path = Path(str(row.get("path", ""))).expanduser().resolve()
        digest = row.get("sha256")
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = file_sha256(path)
        if digest != observed:
            raise ValueError(f"{label} source hash mismatch: {path}")
        verified.append({"path": str(path), "sha256": observed})
    return verified


def _table(
    spec: Any,
    *,
    table_id: str,
    required_columns: list[str],
    optional: bool,
) -> dict[str, Any] | None:
    if spec is None and optional:
        return None
    if not isinstance(spec, dict):
        raise ValueError(f"table {table_id} is required")
    columns = spec.get("columns")
    rows = spec.get("rows")
    if columns != required_columns:
        raise ValueError(f"table {table_id} columns must exactly match the frozen contract")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"table {table_id} requires at least one row")
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != set(columns):
            raise ValueError(f"table {table_id} row {index} does not match columns")
        normalized.append({column: row[column] for column in columns})
    sources = _verify_sources(spec.get("source_artifacts"), f"table {table_id}")
    return {"columns": columns, "rows": normalized, "source_artifacts": sources}


def _write_csv(path: Path, table: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=table["columns"])
        writer.writeheader()
        writer.writerows(table["rows"])


def _markdown_table(table: dict[str, Any]) -> list[str]:
    columns = table["columns"]
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in table["rows"]:
        values = [str(row[column]).replace("|", "\\|") for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return lines


def build_outputs(
    spec: dict[str, Any],
    contract: dict[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate measured inputs and write final tables, narrative, limitations, and index."""
    if spec.get("schema_version") != "v3-final-research-input-v1":
        raise ValueError("unsupported final research input schema")
    source_commit = spec.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("final research input requires full source_commit")
    verdict = spec.get("readiness_verdict")
    if verdict not in {"READY", "READY WITH SCIENTIFIC LIMITATIONS", "BLOCKED / NEGATIVE RESULT"}:
        raise ValueError("invalid readiness verdict")
    narrative = spec.get("narrative")
    if not isinstance(narrative, dict):
        raise ValueError("final research input requires narrative sections")
    for key in ("primary_result", "secondary_results", "robustness", "exposed_report_only"):
        if not isinstance(narrative.get(key), str) or not narrative[key].strip():
            raise ValueError(f"narrative.{key} must be non-empty")

    table_contracts = contract.get("required_tables")
    if not isinstance(table_contracts, dict):
        raise ValueError("final output contract lacks table definitions")
    table_specs = spec.get("tables")
    if not isinstance(table_specs, dict):
        raise ValueError("final research input requires tables")
    tables: dict[str, dict[str, Any] | None] = {}
    for table_id, table_contract in table_contracts.items():
        if not isinstance(table_contract, dict):
            raise ValueError(f"invalid contract for {table_id}")
        required_columns = table_contract.get("required_columns")
        if not isinstance(required_columns, list):
            raise ValueError(f"{table_id} required_columns invalid")
        optional = bool(table_contract.get("optional_when_no_finalist", False))
        tables[table_id] = _table(
            table_specs.get(table_id),
            table_id=table_id,
            required_columns=[str(x) for x in required_columns],
            optional=optional and spec.get("finalist_exists") is not True,
        )

    limitation_keys = contract.get("required_limitations")
    limitations = spec.get("limitations")
    if not isinstance(limitation_keys, list) or not isinstance(limitations, dict):
        raise ValueError("final limitations contract is invalid")
    missing_limits = [
        key
        for key in limitation_keys
        if not isinstance(limitations.get(key), str) or not limitations[key].strip()
    ]
    if missing_limits:
        raise ValueError(f"missing final limitations: {missing_limits}")

    figures = spec.get("figures")
    if not isinstance(figures, list):
        raise ValueError("final research input requires figure registry")
    figure_rows = []
    for index, row in enumerate(figures):
        if not isinstance(row, dict):
            raise ValueError(f"figure {index} must be an object")
        for field in ("figure_id", "path", "source_artifacts", "generation_command", "claim_role"):
            if field not in row:
                raise ValueError(f"figure {index} missing {field}")
        path = Path(str(row["path"])).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        figure_rows.append(
            {
                "figure_id": str(row["figure_id"]),
                "path": str(path),
                "sha256": file_sha256(path),
                "generation_command": str(row["generation_command"]),
                "claim_role": str(row["claim_role"]),
                "source_artifacts": _verify_sources(
                    row["source_artifacts"], f"figure {row['figure_id']}"
                ),
            }
        )

    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite final output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    table_paths: dict[str, str] = {}
    for table_id, table in tables.items():
        if table is None:
            continue
        path = output_dir / f"{table_id.upper()}_TABLE.csv"
        _write_csv(path, table)
        table_paths[table_id] = str(path)

    results_lines = [
        "# Consolidated research results",
        "",
        f"Source commit: `{source_commit}`",
        f"Readiness verdict: **{verdict}**",
        "",
        "## Primary result",
        "",
        narrative["primary_result"].strip(),
        "",
        "## Secondary results",
        "",
        narrative["secondary_results"].strip(),
        "",
        "## Robustness",
        "",
        narrative["robustness"].strip(),
        "",
        "## Exposed report-only 2026 result",
        "",
        narrative["exposed_report_only"].strip(),
        "",
    ]
    for table_id in (
        "survival",
        "model_baseline",
        "cost_execution",
        "action_funnel",
        "feature_causality",
        "robustness",
    ):
        table = tables.get(table_id)
        if table is None:
            continue
        results_lines.extend([f"## {table_id.replace('_', ' ').title()}", ""])
        results_lines.extend(_markdown_table(table))
        results_lines.append("")
    (output_dir / "CONSOLIDATED_RESEARCH_RESULTS.md").write_text(
        "\n".join(results_lines), encoding="utf-8"
    )

    limitations_lines = ["# Known limitations", ""]
    for key in limitation_keys:
        limitations_lines.extend(
            [f"## {str(key).replace('_', ' ').title()}", "", limitations[key].strip(), ""]
        )
    (output_dir / "KNOWN_LIMITATIONS.md").write_text("\n".join(limitations_lines), encoding="utf-8")

    index_lines = [
        "# Research figure/table index",
        "",
        "## Tables",
        "",
        "| ID | Path | Source artifacts |",
        "|---|---|---|",
    ]
    for table_id, path_text in table_paths.items():
        table = tables[table_id]
        source_count = len(table["source_artifacts"]) if table is not None else 0
        index_lines.append(f"| {table_id} | `{path_text}` | {source_count} |")
    index_lines.extend(
        [
            "",
            "## Figures",
            "",
            "| Figure | Path | SHA-256 | Claim role | Generation command |",
            "|---|---|---|---|---|",
        ]
    )
    for row in figure_rows:
        index_lines.append(
            f"| {row['figure_id']} | `{row['path']}` | `{row['sha256']}` | "
            f"{row['claim_role']} | `{row['generation_command']}` |"
        )
    index_lines.append("")
    (output_dir / "THESIS_FIGURE_TABLE_INDEX.md").write_text(
        "\n".join(index_lines), encoding="utf-8"
    )

    readiness_lines = [
        "# Final readiness report",
        "",
        f"Verdict: **{verdict}**",
        "",
        f"Source commit: `{source_commit}`",
        "",
        "The verdict reflects the frozen V3 scientific gates and the canonical artifacts "
        "listed in the final research input manifest. A negative result is a valid final outcome.",
        "",
    ]
    (output_dir / "FINAL_READINESS_REPORT.md").write_text(
        "\n".join(readiness_lines), encoding="utf-8"
    )

    manifest = {
        "schema_version": "v3-final-research-outputs-v1",
        "source_commit": source_commit,
        "readiness_verdict": verdict,
        "finalist_exists": spec.get("finalist_exists") is True,
        "tables": tables,
        "figures": figure_rows,
        "limitations": limitations,
        "outputs": {},
    }
    for path in sorted(output_dir.iterdir()):
        if path.is_file():
            manifest["outputs"][path.name] = {
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
            }
    write_json_atomic(output_dir / "FINAL_OUTPUT_MANIFEST.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise ValueError("final research input must be a JSON object")
    contract_path = args.contract if args.contract.is_absolute() else ROOT / args.contract
    contract = OmegaConf.to_container(OmegaConf.load(contract_path), resolve=True)
    if (
        not isinstance(contract, dict)
        or not all(isinstance(key, str) for key in contract)
        or contract.get("schema_version") != "v3-final-output-contract-v1"
    ):
        raise ValueError("unsupported final output contract")
    manifest = build_outputs(
        spec,
        {str(key): value for key, value in contract.items()},
        output_dir=args.output_dir.expanduser().resolve(),
    )
    print(
        json.dumps(
            {"output_dir": str(args.output_dir), "outputs": sorted(manifest["outputs"])}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
