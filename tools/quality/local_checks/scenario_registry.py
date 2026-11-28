"""Map reviewed product requirements to exact pytest evidence and hardware scope."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from tools.quality.local_checks.run_evidence import HERE, ROOT, read_quality_json, verify_quality_manifest, quality_source_identity


def _valid_scenario_selector(selector: str) -> bool:
    """Verify path and optional class/function names without importing product modules."""
    path, *names = selector.split("::")
    source = ROOT / path
    if not source.is_file() or not source.resolve().is_relative_to(ROOT / "tests"):
        return False
    if not names:
        return source.name.startswith("test_")
    nodes = ast.parse(source.read_text()).body
    for name in names:
        matches = [node for node in nodes if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == name]
        if len(matches) != 1:
            return False
        nodes = matches[0].body
    return names[-1].startswith("test_")


def scenario_selectors(domain: str | None, platform: str) -> list[str]:
    """Return reviewed selectors for the requested domain and execution platform."""
    registry = read_quality_json(HERE / "scenarios.json")
    selectors = {s for row in registry if (domain is None or row["domain"] == domain)
                 and row["platform"] == platform for s in row["selectors"]}
    if any(not _valid_scenario_selector(s) for s in selectors):
        raise ValueError("Scenario registry has stale test mappings")
    return sorted(selectors)


def report_semantic_scenarios(
    manifest_path: Path | None, domain: str | None, platform: str
) -> dict[str, Any]:
    """Distinguish registration, mapping, collection and verified per-test outcomes."""
    registry = read_quality_json(HERE / "scenarios.json")
    if len({row["id"] for row in registry}) != len(registry):
        raise ValueError("Duplicate semantic scenario")
    outcomes: dict[str, Any] = {}
    source = None
    if manifest_path:
        verify_quality_manifest(manifest_path)
        source = read_quality_json(manifest_path)
        if source.get("tree_sha256") != quality_source_identity()["tree_sha256"]:
            raise ValueError("Scenario evidence belongs to a different source tree")
        if source["execution_status"] not in {"ok", "findings"}:
            raise ValueError("Incomplete execution evidence")
        if source["result"].get("validation_platform", "cpu") != platform:
            raise ValueError("Evidence belongs to another validation platform")
        for artifact in source["artifacts"]:
            if artifact.endswith("-outcomes.json") or artifact.endswith("/outcomes.json"):
                for node, value in read_quality_json(manifest_path.parent / artifact).items():
                    if node in outcomes:
                        raise ValueError("Duplicate scenario test receipt")
                    outcomes[node] = value
    result = []
    for row in registry:
        if domain and row["domain"] != domain:
            continue
        selectors = row["selectors"]
        complete_scope = source is not None and (source["result"].get("scope") == "full" or (source.get("action") == "semantic" and set(selectors).issubset(source["result"].get("scenario_selectors", []))))
        missing = [s for s in selectors if not _valid_scenario_selector(s)]
        relevant = {s: [n for n in outcomes if n == s or n.startswith(s+"::") or n.startswith(s+"[")]
                    for s in selectors}
        executed = {n: outcomes[n]["status"] for nodes in relevant.values() for n in nodes}
        status = (
            "unmapped" if not selectors else
            "stale_mapping" if missing else
            "platform_not_checked" if row["platform"] != platform else
            "failed" if "failed" in executed.values() else
            "passed" if complete_scope and all(relevant.values()) and executed and set(executed.values()) == {"passed"} else
            "partial_or_skipped" if executed else "mapped_unexecuted"
        )
        result.append({**row, "status": status, "missing_selectors": missing, "outcomes": executed})
    return {"status": "findings" if any(r["status"] in {"stale_mapping", "failed"} for r in result) else "ok",
            "scenarios": result, "counts": {s: sum(r["status"] == s for r in result)
            for s in sorted({r["status"] for r in result})},
            "source_commit": source.get("source_commit") if source else None,
            "qualification": "A mapped test is not a passed scenario; hardware evidence remains distinct."}
