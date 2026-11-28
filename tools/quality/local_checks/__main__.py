"""Opt-in local quality commands; existing required CI remains authoritative."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from tools.quality.local_checks.run_evidence import (
    HERE,
    OUTPUT,
    ROOT,
    create_quality_run,
    publish_quality_manifest,
    quality_source_identity,
    quality_timestamp,
    read_quality_json,
    run_quality_process,
    verify_quality_manifest,
    write_quality_json,
)

PROPERTY_TARGETS = ("all", "risk", "actions", "ticks", "chronology", "accounting", "provenance")
POLICY_ACTIONS = {
    "coverage-diff": "diff",
    "baseline-candidate": "coverage",
    "exclusions": "coverage",
    "product-parity": "parity",
    "differential": "parity",
    "import-findings": "static",
    "mutation-import": "mutation",
    "coverity": "static",
    "codeql": "static",
}


def _test_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common bounded test selection and resource controls."""
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument(
        "--marker", default="unit and not slow and not gpu and not triton and not research"
    )
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--worker-mib", type=int, default=1024)
    parser.add_argument("--history", type=Path, action="append", default=[])
    parser.add_argument("--no-affinity", action="store_true")


def quality_parser() -> argparse.ArgumentParser:
    """Build the local command interface without installing or invoking tools."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=180, help="seconds per external process")
    sub = parser.add_subparsers(dest="action", required=True)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--versions", action="store_true")
    for name in ("inventory", "repo-audit", "debt"):
        sub.add_parser(name)
    coverage = sub.add_parser("coverage")
    coverage.add_argument("--full", action="store_true")
    coverage.add_argument("--test", action="append", default=[])
    coverage.add_argument("--workers", type=int, default=1)
    coverage.add_argument("--worker-mib", type=int, default=1024)
    coverage.add_argument("--base", default="main")
    coverage.add_argument("--baseline-manifest", type=Path)
    diff = sub.add_parser("coverage-diff")
    diff.add_argument("report", type=Path)
    diff.add_argument("--base", default="main")
    baseline = sub.add_parser("baseline-candidate")
    baseline.add_argument("manifest", type=Path)
    baseline.add_argument("--ref", default="main")
    exclusions = sub.add_parser("exclusions")
    exclusions.add_argument("--base", default="main")
    impact = sub.add_parser("impacted")
    impact.add_argument("manifest", type=Path)
    impact.add_argument("--base", default="main")
    static = sub.add_parser("static")
    static.add_argument("tools", nargs="*")
    static.add_argument("--profile", default="fast")
    coverity = sub.add_parser("coverity")
    coverity.add_argument("--config", type=Path)
    coverity.add_argument("--build", nargs="+", default=[])
    codeql = sub.add_parser("codeql")
    codeql.add_argument("--language", default="python")
    codeql.add_argument(
        "--query", default="codeql/python-queries:codeql-suites/python-code-scanning.qls"
    )
    codeql.add_argument("--build")
    codeql.add_argument("--threads", type=int, default=2)
    finding = sub.add_parser("import-findings")
    finding.add_argument("tool")
    finding.add_argument("report", type=Path)
    mutation = sub.add_parser("mutation")
    mutation.add_argument("--scope", default="configured")
    mutation.add_argument("--test", action="append", default=[])
    mutation.add_argument("--children", type=int, default=2)
    mutation.add_argument("--include-uncovered", action="store_true")
    mutation.add_argument("--pattern", action="append", default=[])
    imported = sub.add_parser("mutation-import")
    imported.add_argument("tool", choices=["mutmut", "cargo-mutants"])
    imported.add_argument("report", type=Path)
    imported.add_argument("--scope", type=Path, required=True)
    imported.add_argument("--details", type=Path)
    imported.add_argument("--complete", action="store_true")
    for name in ("properties", "fuzz"):
        target = sub.add_parser(name)
        target.add_argument("--target", choices=PROPERTY_TARGETS, default="all")
        target.add_argument("--profile", choices=["dev", "pr", "nightly"], default="dev")
        target.add_argument("--seed", type=int, default=42)
        target.add_argument("--seconds", type=int, default=10)
        target.add_argument("--corpus", type=Path)
    semantic = sub.add_parser("semantic")
    semantic.add_argument("--domain")
    semantic.add_argument("--platform", choices=["cpu", "cuda", "rocm"], default="cpu")
    semantic.add_argument("--manifest", type=Path)
    semantic.add_argument("--run", action="store_true")
    parity = sub.add_parser("product-parity")
    parity.add_argument(
        "pair", choices=["frame-bundle", "gym-transition", "backtest", "rollout-buffer", "ppo-math"]
    )
    differential = sub.add_parser("differential")
    differential.add_argument("reference", type=Path)
    differential.add_argument("candidate", type=Path)
    differential.add_argument("--fields", type=Path)
    native = sub.add_parser("native")
    native.add_argument("profile", nargs="?", default="inventory")
    native.add_argument("check", nargs="?", default="inventory")
    native.add_argument("--target")
    native.add_argument("--arguments", nargs=argparse.REMAINDER, default=[])
    environment = sub.add_parser("environment")
    environment.add_argument("profile", choices=["analyzers", "cpu", "gpu"])
    environment.add_argument("operation", choices=["plan", "resolve", "sync"])
    environment.add_argument("--allow-drift", action="store_true")
    cache = sub.add_parser("cache")
    cache.add_argument("--profile", default="gpu")
    cache.add_argument("--lock", type=Path, default=ROOT / "uv.lock")
    _test_arguments(sub.add_parser("test-inventory"))
    _test_arguments(sub.add_parser("test-shards"))
    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--branch")
    dashboard.add_argument("--commit")
    dashboard.add_argument("--action-filter")
    dashboard.add_argument("--parquet", action="store_true")
    perf = sub.add_parser("performance")
    perf.add_argument("before", type=Path)
    perf.add_argument("after", type=Path)
    perf.add_argument("--metrics", type=Path, required=True)
    perf.add_argument("--max-regression", type=float, default=0.05)
    verify = sub.add_parser("verify")
    verify.add_argument("manifest", type=Path)
    return parser


def _coverage_command(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """Collect explicit coverage and compare only compatible scopes against target evidence."""
    from tools.quality.local_checks.coverage_tools import (
        analyze_local_coverage,
        collect_local_coverage,
    )
    from tools.quality.local_checks.resources import discover_worker_capacity

    capacity = discover_worker_capacity(args.workers, args.worker_mib)
    if not capacity["workers"]:
        return {"status": "insufficient_resources", "capacity": capacity}
    result = collect_local_coverage(out, args.test, args.full, args.timeout, capacity["workers"])
    result["capacity"] = capacity
    if result["status"] == "ok":
        analysis = analyze_local_coverage(
            out / "coverage.json", args.base, args.full, args.baseline_manifest
        )
        result["analysis"] = analysis
        result["status"] = analysis["status"]
    return result


def _test_command(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """Run an inventory or execute an explicitly selected bounded shard campaign."""
    from tools.quality.local_checks.test_scheduling import (
        collect_test_inventory,
        run_balanced_test_shards,
    )

    paths = args.path or ["tests/unit"]
    if args.action == "test-inventory":
        return collect_test_inventory(out, args.timeout, paths, args.marker)
    return run_balanced_test_shards(
        out,
        args.timeout,
        paths,
        args.marker,
        args.count,
        args.workers,
        args.worker_mib,
        args.history,
        not args.no_affinity,
    )


def _semantic_command(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """Report existing scenario evidence or run the registered CPU selectors only."""
    from tools.quality.local_checks.scenario_registry import (
        report_semantic_scenarios,
        scenario_selectors,
    )
    from tools.quality.local_checks.test_scheduling import run_balanced_test_shards

    if args.run:
        if args.manifest:
            raise ValueError("Choose a run or imported manifest, not both")
        selectors = scenario_selectors(args.domain, args.platform)
        if args.platform != "cpu" or not selectors:
            return {
                "status": "not_run",
                "reason": "No registered executable hardware scenario suite",
            }
        # A whole-file selector subsumes all node selectors in the same file.
        selected = [s for s in selectors if "::" not in s or s.split("::", 1)[0] not in selectors]
        result = run_balanced_test_shards(
            out,
            args.timeout,
            sorted(set(selected)),
            "not slow and not gpu and not triton and not research",
            1,
            1,
            1024,
            [],
            True,
        )
        result["validation_platform"] = "cpu"
        result["scenario_domain"] = args.domain
        result["scenario_selectors"] = selectors
        return result
    return report_semantic_scenarios(args.manifest, args.domain, args.platform)


def _product_parity_command(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """Invoke the repository's actual backend parity tests and preserve their receipts."""
    from tools.quality.local_checks.test_scheduling import run_balanced_test_shards

    suites = {
        "frame-bundle": ["tests/unit/simulation/test_environment/test_bundle_env_equivalence.py"],
        "gym-transition": [
            "tests/unit/simulation/test_environment/test_simulation_transition_contract.py"
        ],
        "backtest": ["tests/integration/backtest/test_account_transition_parity.py"],
        "rollout-buffer": ["tests/unit/models/test_rollout_copy.py"],
        "ppo-math": [
            "tests/unit/learning/test_update_graph_fake_capture.py",
            "tests/unit/tooling/test_local_quality_product_oracles.py::test_gae_finite_horizon_oracle",
        ],
    }
    result = run_balanced_test_shards(
        out,
        args.timeout,
        suites[args.pair],
        "not slow and not gpu and not triton and not research",
        1,
        1,
        1024,
        [],
        True,
    )
    return {**result, "backend_pair": args.pair, "validation_platform": "cpu"}


def _analysis_command(
    args: argparse.Namespace, out: Path, policy: dict[str, Any]
) -> dict[str, Any]:
    """Route explicitly selected analyzer and mutation commands."""
    from tools.quality.local_checks.analyzer_execution import (
        publish_analyzer_findings,
        quality_tool_doctor,
        run_local_codeql,
        run_local_coverity,
        run_static_analyzers,
    )
    from tools.quality.local_checks.mutation_campaign import run_python_mutation
    from tools.quality.local_checks.mutation_results import import_mutation_results
    from tools.quality.local_checks.normalization import read_analyzer_report

    match args.action:
        case "doctor":
            return quality_tool_doctor(out, args.timeout, args.versions)
        case "static":
            return run_static_analyzers(
                out, args.timeout, args.tools or policy["profiles"][args.profile]
            )
        case "coverity":
            return run_local_coverity(out, args.timeout, args.config, args.build)
        case "codeql":
            return run_local_codeql(
                out, args.timeout, args.language, args.query, args.build, args.threads
            )
        case "import-findings":
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.tool):
                raise ValueError("Invalid analyzer identifier")
            rows = read_analyzer_report(args.tool, args.report, ROOT)
            publish_analyzer_findings(out, args.tool, rows)
            return {
                "status": "findings" if rows else "ok",
                "count": len(rows),
                "scope": "imported unverified source",
            }
        case "mutation":
            return run_python_mutation(
                out,
                args.timeout,
                args.scope,
                args.test,
                args.children,
                args.include_uncovered,
                args.pattern,
            )
        case "mutation-import":
            return import_mutation_results(
                args.report, args.tool, read_quality_json(args.scope), args.complete, args.details
            )
        case _:
            raise ValueError("Unknown analysis action")


def _coverage_reporting_command(args: argparse.Namespace) -> dict[str, Any]:
    """Route report-only coverage and impact operations."""
    from tools.quality.local_checks.coverage_governance import (
        audit_quality_exclusions,
        source_quality_inventory,
        verified_baseline_candidate,
    )
    from tools.quality.local_checks.coverage_tools import analyze_local_coverage
    from tools.quality.local_checks.impact import plan_impacted_tests

    match args.action:
        case "inventory":
            return source_quality_inventory()
        case "coverage-diff":
            return {
                **analyze_local_coverage(args.report, args.base, False),
                "qualification": "Imported report; source identity unverified",
            }
        case "baseline-candidate":
            return verified_baseline_candidate(args.manifest, args.ref)
        case "exclusions":
            return audit_quality_exclusions(args.base)
        case "impacted":
            directory = args.manifest.parent
            return {
                "status": "ok",
                **plan_impacted_tests(
                    ROOT,
                    args.base,
                    directory / "test-inventory.json",
                    directory / ".coverage",
                    args.manifest,
                ),
            }
        case _:
            raise ValueError("Unknown coverage report action")


def _other_quality_command(args: argparse.Namespace, out: Path) -> dict[str, Any]:
    """Route optional environments, native tooling, dashboards and property campaigns."""
    from tools.quality.local_checks.dependency_profiles import configure_dependency_profile
    from tools.quality.local_checks.native_execution import (
        discover_native_components,
        run_native_profile,
    )
    from tools.quality.local_checks.quality_reporting import (
        compare_performance_evidence,
        generate_quality_dashboard,
    )
    from tools.quality.local_checks.trace_comparison import compare_trace_files

    match args.action:
        case "environment":
            return configure_dependency_profile(
                out, args.timeout, args.profile, args.operation, args.allow_drift
            )
        case "native":
            if args.profile == "inventory":
                return {"status": "ok", "components": discover_native_components()}
            return run_native_profile(
                out, args.timeout, args.profile, args.check, args.target, args.arguments
            )
        case "dashboard":
            return generate_quality_dashboard(
                out, args.branch, args.commit, args.action_filter, args.parquet
            )
        case "performance":
            return compare_performance_evidence(
                args.before, args.after, read_quality_json(args.metrics), args.max_regression
            )
        case "differential":
            return compare_trace_files(args.reference, args.candidate, args.fields)
        case "properties" | "fuzz":
            corpus = args.corpus or OUTPUT / "corpora" / args.target
            engine = "hypothesis" if args.action == "properties" else "atheris"
            command = [
                sys.executable,
                "-m",
                "tools.quality.local_checks.property_campaign",
                engine,
                "--target",
                args.target,
                "--profile",
                args.profile,
                "--seed",
                str(args.seed),
                "--seconds",
                str(args.seconds),
                "--corpus",
                str(corpus),
            ]
            return run_quality_process(command, out / f"{engine}.log", args.timeout)
        case "debt":
            from tools.quality.local_checks.debt_analysis import audit_technical_debt

            return audit_technical_debt()
        case "repo-audit":
            from tools.quality.repository_audit import build_audit

            return {"status": "ok", "audit": build_audit(ROOT)}
        case "cache":
            from tools.quality.local_checks.resources import quality_cache_key
            from tools.quality.local_checks.run_evidence import quality_tool_versions

            versions = {k: v for k, v in quality_tool_versions().items() if v is not None}
            return {
                "status": "ok",
                "cache_key": quality_cache_key(args.lock, args.profile, versions),
            }
        case "verify":
            return verify_quality_manifest(args.manifest)
        case _:
            raise ValueError("Unknown quality action")


def _dispatch_quality_action(
    args: argparse.Namespace, out: Path, policy: dict[str, Any]
) -> dict[str, Any]:
    """Dispatch a single explicit local action without any automatic full campaign."""
    if args.action == "coverage":
        return _coverage_command(args, out)
    if args.action in {"test-inventory", "test-shards"}:
        return _test_command(args, out)
    if args.action == "semantic":
        return _semantic_command(args, out)
    if args.action == "product-parity":
        return _product_parity_command(args, out)
    if args.action in {
        "doctor",
        "static",
        "coverity",
        "codeql",
        "import-findings",
        "mutation",
        "mutation-import",
    }:
        return _analysis_command(args, out, policy)
    if args.action in {
        "inventory",
        "coverage-diff",
        "baseline-candidate",
        "exclusions",
        "impacted",
    }:
        return _coverage_reporting_command(args)
    return _other_quality_command(args, out)


def main() -> int:
    """Run a command and publish evidence; findings are advisory by default."""
    args = quality_parser().parse_args()
    if args.timeout < 1:
        raise ValueError("Timeout must be positive")
    policy = read_quality_json(HERE / "policy.json")
    mode = policy["enforcement"].get(POLICY_ACTIONS.get(args.action, args.action), "advisory")
    if mode not in {"off", "advisory", "blocking"}:
        raise ValueError("Unsupported enforcement mode")
    out = create_quality_run()
    before, started = quality_source_identity(), quality_timestamp()
    try:
        result = (
            {"status": "disabled"} if mode == "off" else _dispatch_quality_action(args, out, policy)
        )
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError) as exc:
        result = {"status": "error", "error": str(exc)}
    write_quality_json(out / "result.json", result)
    manifest = publish_quality_manifest(out, before, started, args.action, result, mode)
    status = manifest["execution_status"]
    print(
        json.dumps(
            {"status": status, "mode": mode, "manifest": str(out / "manifest.json")}, indent=2
        )
    )
    if status == "findings":
        return int(mode == "blocking")
    return 0 if status in {"ok", "disabled", "not_applicable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
