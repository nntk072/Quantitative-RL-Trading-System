"""Consolidate verified local run evidence into JSON, HTML and optional analytical data."""

from __future__ import annotations

import html
import importlib
import json
from pathlib import Path
from typing import Any

from tools.quality.local_checks.run_evidence import (
    OUTPUT, read_quality_json, verify_quality_manifest, write_quality_json,
)


def collect_quality_history(branch: str | None, commit: str | None, action: str | None) -> list[dict[str, Any]]:
    """Read existing immutable run manifests; mark invalid evidence instead of treating it as clean."""
    result = []
    for path in sorted(OUTPUT.glob("*/manifest.json")):
        try:
            row = read_quality_json(path)
            if branch and row.get("source_branch") != branch:
                continue
            if commit and row.get("source_commit") != commit:
                continue
            if action and row.get("action") != action:
                continue
            verify_quality_manifest(path)
            result.append({"manifest": str(path), "integrity": "verified", **row})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result.append({"manifest": str(path), "integrity": "invalid",
                           "execution_status": "unavailable", "error": str(exc)})
    return result


def _history_metric_rows(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten coverage metrics with package and commit identities, preserving null ratios."""
    rows = []
    for run in history:
        if run["integrity"] != "verified":
            continue
        result = run.get("result", {})
        summary = result.get("summary") or result.get("analysis", {}).get("summary")
        if not summary:
            continue
        for name, values in {"overall": summary["overall"], **summary["packages"]}.items():
            rows.append({"run_id": run["run_id"], "commit": run["source_commit"],
                         "branch": run["source_branch"], "scope": result.get("scope"),
                         "package": name, "statement_ratio": values.get("line_ratio"),
                         "branch_ratio": values.get("branch_ratio")})
    return rows


def generate_quality_dashboard(
    out: Path, branch: str | None, commit: str | None, action: str | None, parquet: bool
) -> dict[str, Any]:
    """Generate static evidence reports and optional DuckDB/Parquet tables from actual results."""
    history = collect_quality_history(branch, commit, action)
    metrics = _history_metric_rows(history)
    write_quality_json(out/"history.json", history)
    write_quality_json(out/"metrics.json", metrics)
    columns = ("run_id", "source_branch", "source_commit", "action", "started_at", "execution_status", "integrity")
    header = "".join(f"<th>{html.escape(key)}</th>" for key in columns)
    body = "".join("<tr>"+"".join("<td>"+html.escape(str(row.get(key, "unavailable")))+"</td>"
                                  for key in columns)+"</tr>" for row in reversed(history))
    metric_rows = "".join("<tr>"+"".join("<td>"+html.escape(str(row.get(key, "unavailable")))+"</td>"
                  for key in ("run_id","package","scope","statement_ratio","branch_ratio"))+"</tr>"
                  for row in metrics)
    details = html.escape(json.dumps(history, indent=2, ensure_ascii=True))
    (out/"index.html").write_text("<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>Quant quality evidence</title><style>body{font:15px system-ui;margin:2rem;max-width:120rem}"
        "table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:.5rem;border-bottom:1px solid #aaa;"
        "text-align:left;overflow-wrap:anywhere}pre{white-space:pre-wrap}</style><h1>Local quality evidence</h1>"
        "<p>Measured evidence only. Missing or invalid evidence is not a pass. Statement and branch ratios are fractions.</p>"
        "<h2>Runs</h2><table><thead><tr>"+header+"</tr></thead><tbody>"+body+"</tbody></table>"
        "<h2>Coverage by package</h2><table><thead><tr><th>Run</th><th>Package</th><th>Scope</th>"
        "<th>Statement</th><th>Branch</th></tr></thead><tbody>"+metric_rows+"</tbody></table>"
        "<details><summary>All normalized run results</summary><pre>"+details+"</pre></details></html>", encoding="utf-8")
    if parquet:
        try:
            duckdb = importlib.import_module("duckdb")
        except ImportError:
            return {"status": "missing_tool", "html": str(out/"index.html"), "reason": "Install DuckDB in the selected environment"}
        db = duckdb.connect(str(out/"quality.duckdb"))
        try:
            db.execute("create table coverage(run_id varchar, commit_sha varchar, branch varchar, scope varchar, package varchar, statement_ratio double, branch_ratio double)")
            if metrics:
                db.executemany("insert into coverage values (?, ?, ?, ?, ?, ?, ?)",
                    [[row[k] for k in ("run_id","commit","branch","scope","package","statement_ratio","branch_ratio")] for row in metrics])
            db.execute("create table runs(run_id varchar, branch varchar, commit_sha varchar, action varchar, status varchar, integrity varchar, manifest_json varchar)")
            if history:
                db.executemany("insert into runs values (?, ?, ?, ?, ?, ?, ?)",
                    [[row.get("run_id"), row.get("source_branch"), row.get("source_commit"), row.get("action"),
                      row.get("execution_status"), row["integrity"], json.dumps(row)] for row in history])
            for table in ("coverage", "runs"):
                destination = str(out/f"{table}.parquet").replace("'", "''")
                db.execute(f"copy {table} to '{destination}' (format parquet)")
        finally:
            db.close()
    return {"status": "ok", "runs": len(history), "metric_rows": len(metrics),
            "invalid_runs": sum(r["integrity"] != "verified" for r in history),
            "html": str(out/"index.html"), "parquet": parquet}


def compare_performance_evidence(before: Path, after: Path, metrics: dict[str, str],
                                 maximum_regression: float) -> dict[str, Any]:
    """Compare explicitly named comparable benchmark metrics without launching benchmarks."""
    if not 0 <= maximum_regression < 1 or not metrics:
        raise ValueError("Invalid performance policy")
    a, b = read_quality_json(before), read_quality_json(after)
    if a.get("benchmark_identity") != b.get("benchmark_identity") or not a.get("benchmark_identity"):
        raise ValueError("Benchmark configurations, workload and hardware identity must match")
    comparisons = []
    for key, direction in metrics.items():
        old, new = a["metrics"][key], b["metrics"][key]
        if direction not in {"higher", "lower"} or old <= 0 or new <= 0:
            raise ValueError(f"Invalid comparable metric: {key}")
        import math

        if not math.isfinite(old) or not math.isfinite(new):
            raise ValueError("Nonfinite performance evidence")
        regression = (old-new)/old if direction == "higher" else (new-old)/old
        comparisons.append({"metric": key, "before": old, "after": new,
                            "regression_fraction": regression, "regressed": regression > maximum_regression})
    return {"status": "findings" if any(r["regressed"] for r in comparisons) else "ok",
            "comparisons": comparisons, "qualification": "Imported measurements; no benchmark execution."}
