"""Command-line interface for the active research workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.research.catalog import DEFAULT_CATALOG, load_research_catalog
from experiments.research.compute_budget import build_compute_budget
from experiments.research.execution import execute_command_bundle
from experiments.research.history import DEFAULT_HISTORY, load_history, render_markdown
from experiments.research.portfolio import summarize_portfolio_safety
from experiments.research.primary_comparison import analyze_primary_payload, build_primary_payload
from experiments.research.readiness import (
    DEFAULT_READINESS,
    build_readiness,
    load_readiness_contract,
    record_review,
)
from experiments.research.release import assemble_release
from experiments.research.repeatability import summarize_repeatability
from experiments.research.reporting import consolidate_execution_manifests
from experiments.research.reporting_tables import build_research_tables
from experiments.research.robustness import summarize_robustness
from experiments.research.workflow import freeze_experiment, load_bundle, write_bundle


def _finalist_runs(values: list[str] | None) -> dict[int, Path] | None:
    """Parse repeated seed-to-run path arguments.

    Args:
        values: Value used for values.

    Returns:
        Result produced by _finalist_runs.
    """
    if values is None:
        return None
    result: dict[int, Path] = {}
    for value in values:
        raw_seed, separator, raw_path = value.partition("=")
        if not separator:
            raise ValueError("--finalist-run entries must use SEED=PATH")
        seed = int(raw_seed)
        if seed in result:
            raise ValueError(f"duplicate finalist seed: {seed}")
        result[seed] = Path(raw_path)
    return result


def _named_json(values: list[str]) -> dict[str, dict[str, object]]:
    """Load named JSON objects from NAME=PATH arguments.

    Args:
        values: Value used for values.

    Returns:
        Result produced by _named_json.
    """
    result: dict[str, dict[str, object]] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if not separator or not name.strip():
            raise ValueError("named JSON inputs must use NAME=PATH")
        path = Path(raw_path).expanduser().resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"named JSON input must be an object: {path}")
        if name in result:
            raise ValueError(f"duplicate named JSON input: {name}")
        result[name] = payload
    return result


def _json_object(path: Path) -> dict[str, object]:
    """Load one JSON object from disk.

    Args:
        path: Path to the input or output artifact.

    Returns:
        Result produced by _json_object.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    """Run catalog, freeze, execute, consolidate, history, or release operations.

    Args:
        argv: Command-line arguments for this operation.

    Returns:
        Result produced by main.
    """
    parser = argparse.ArgumentParser(description="Research experiment workflow")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subparsers.add_parser("catalog", help="show registered experiments")
    catalog_parser.add_argument("--domain", default=None)
    catalog_parser.add_argument("--component", default=None, help="filter by reusable component")

    freeze = subparsers.add_parser("freeze", help="freeze one experiment into a command bundle")
    freeze.add_argument("experiment")
    freeze.add_argument("--assembly", help="select a named combination of component variants")
    freeze.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Freeze only the named variant; repeat to select multiple variants.",
    )
    freeze.add_argument(
        "--component",
        action="append",
        default=[],
        help="Freeze variants assigned to a component; repeat for multiple components.",
    )
    freeze.add_argument("--output-root", default="outputs/research")
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--readiness", type=Path)
    freeze.add_argument("--survival-gate", type=Path)
    freeze.add_argument("--finalist-run", action="append")
    freeze.add_argument("--robustness-record", type=Path)
    freeze.add_argument("--exposure-marker", type=Path)

    execute = subparsers.add_parser("execute", help="execute a frozen research bundle")
    execute.add_argument("--bundle", type=Path, required=True)
    execute.add_argument("--run-root", type=Path, required=True)
    execute.add_argument("--max-workers", type=int, default=1)
    execute.add_argument("--allow-experiments", action="store_true")
    execute.add_argument("--resume", action="store_true")
    execute.add_argument("--retry-failed", action="store_true")
    execute.add_argument("--max-runtime-seconds", type=float, default=None)

    consolidate = subparsers.add_parser(
        "consolidate",
        help="merge execution manifests into one domain-oriented result catalog",
    )
    consolidate.add_argument("--execution", type=Path, action="append", required=True)
    consolidate.add_argument("--output", type=Path, required=True)

    history = subparsers.add_parser(
        "history",
        help="render the normalized historical evidence catalog",
    )
    history.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    history.add_argument("--output", type=Path)

    review = subparsers.add_parser("review", help="record one source-bound scientific review")
    review.add_argument("--id", required=True)
    review.add_argument("--status", choices=("pass", "fail"), required=True)
    review.add_argument("--reviewed-by", required=True)
    review.add_argument("--note", required=True)
    review.add_argument("--evidence", type=Path, action="append", required=True)
    review.add_argument("--output", type=Path, required=True)

    readiness = subparsers.add_parser("readiness", help="build scientific training authorization")
    readiness.add_argument("--contract", type=Path, default=DEFAULT_READINESS)
    readiness.add_argument("--execution", action="append", default=[], metavar="EXPERIMENT=PATH")
    readiness.add_argument("--review", action="append", default=[], metavar="REVIEW=PATH")
    readiness.add_argument("--output", type=Path, required=True)

    repeatability = subparsers.add_parser("repeatability", help="summarize repeatability execution")
    repeatability.add_argument("--execution", type=Path, required=True)
    repeatability.add_argument("--output", type=Path, required=True)

    portfolio_safety = subparsers.add_parser(
        "portfolio-safety",
        help="verify hard-risk safety for all six portfolio treatment runs",
    )
    portfolio_safety.add_argument("--run", action="append", required=True, metavar="SEED=PATH")
    portfolio_safety.add_argument("--output", type=Path, required=True)

    robustness = subparsers.add_parser(
        "robustness",
        help="summarize account and execution robustness executions",
    )
    robustness.add_argument("--execution", type=Path, action="append", required=True)
    robustness.add_argument("--output", type=Path, required=True)

    primary = subparsers.add_parser("primary", help="validate and analyze six paired primary paths")
    primary.add_argument("--source", type=Path, required=True)
    primary.add_argument("--payload", type=Path, required=True)
    primary.add_argument("--analysis", type=Path, required=True)

    tables = subparsers.add_parser("tables", help="build report-ready result inventories")
    tables.add_argument("--results", type=Path, required=True)
    tables.add_argument("--output", type=Path, required=True)

    compute = subparsers.add_parser("compute-budget", help="build semantic training budget")
    compute.add_argument("--decisions-per-full-path", type=int, required=True)
    compute.add_argument("--wf-decisions-per-full-path", type=int, nargs="+", required=True)
    compute.add_argument("--n-envs", type=int, nargs="+", default=[8, 16, 32, 64])
    compute.add_argument("--rollout-steps-per-env", type=int, required=True)
    compute.add_argument("--batch-size", type=int, required=True)
    compute.add_argument("--epochs", type=int, required=True)
    compute.add_argument("--supplied-total-timesteps", type=int)
    compute.add_argument("--fps", action="append", default=[])
    compute.add_argument("--output", type=Path, required=True)

    release = subparsers.add_parser("release", help="assemble immutable research evidence")
    release.add_argument("--results", type=Path, required=True)
    release.add_argument("--protocol", type=Path, required=True)
    release.add_argument("--output", type=Path, required=True)
    release.add_argument("--extra", type=Path, action="append", default=[])

    args = parser.parse_args(argv)
    catalog = load_research_catalog(args.catalog)

    if args.command == "catalog":
        experiments = (
            catalog.by_domain(args.domain) if args.domain is not None else catalog.experiments
        )
        catalog_rows = []
        for item in experiments:
            variants = [
                variant
                for variant in item.variants
                if args.component is None or variant.component == args.component
            ]
            if not variants:
                continue
            components = {
                component: [
                    variant.variant_id for variant in variants if variant.component == component
                ]
                for component in sorted({variant.component for variant in variants})
            }
            catalog_rows.append(
                {
                    "experiment": item.experiment_id,
                    "domain": item.domain,
                    "selection_role": item.selection_role,
                    "variants": [variant.variant_id for variant in variants],
                    "components": components,
                    "assemblies": item.assemblies,
                    "execution": item.execution.kind,
                }
            )
        print(json.dumps(catalog_rows, indent=2))
        return 0
    if args.command == "freeze":
        experiment = catalog.experiment(args.experiment)
        if args.assembly and (args.variant or args.component):
            raise ValueError("--assembly cannot be combined with --variant or --component")
        if args.assembly and args.assembly not in experiment.assemblies:
            raise ValueError(f"{args.experiment} has no assembly named {args.assembly!r}")
        selected = set(experiment.assemblies[args.assembly]) if args.assembly else set(args.variant)
        if selected:
            unknown = selected - {item.variant_id for item in experiment.variants}
            if unknown:
                raise ValueError(f"{args.experiment} has no variants named {sorted(unknown)}")
        if args.component:
            matching = {
                item.variant_id for item in experiment.variants if item.component in args.component
            }
            selected = selected & matching if selected else matching
            if not selected:
                raise ValueError(f"{args.experiment} has no matching component variants")
        bundle = freeze_experiment(
            catalog,
            args.experiment,
            output_root=args.output_root,
            readiness=args.readiness,
            survival_gate=args.survival_gate,
            finalist_runs=_finalist_runs(args.finalist_run),
            robustness_record=args.robustness_record,
            exposure_marker=args.exposure_marker,
            selected_variants=tuple(sorted(selected)),
        )
        write_bundle(bundle, args.output)
        print(json.dumps({"bundle": str(args.output), "commands": len(bundle.commands)}, indent=2))
        return 0
    if args.command == "execute":
        result = execute_command_bundle(
            load_bundle(args.bundle),
            run_root=args.run_root,
            max_workers=args.max_workers,
            allow_experiments=args.allow_experiments,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_runtime_seconds=args.max_runtime_seconds,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "passed" else 2 if result["status"] == "incomplete" else 1
    if args.command == "consolidate":
        result = consolidate_execution_manifests(args.execution, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "history":
        text = render_markdown(load_history(args.history))
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    if args.command == "review":
        result = record_review(
            review_id=args.id,
            status=args.status,
            reviewed_by=args.reviewed_by,
            note=args.note,
            evidence=args.evidence,
            output=args.output,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "readiness":
        result = build_readiness(
            contract=load_readiness_contract(args.contract),
            execution_manifests=_named_json(args.execution),
            reviews=_named_json(args.review),
        )
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "repeatability":
        result = summarize_repeatability(args.execution)
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "portfolio-safety":
        runs = _finalist_runs(args.run)
        if runs is None:
            raise ValueError("portfolio-safety requires seed paths")
        result = summarize_portfolio_safety(runs)
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "robustness":
        result = summarize_robustness(args.execution)
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "pass" else 1
    if args.command == "primary":
        payload = build_primary_payload(_json_object(args.source))
        analysis = analyze_primary_payload(payload)
        from artifacts.atomic import write_json_atomic

        args.payload.parent.mkdir(parents=True, exist_ok=True)
        args.analysis.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.payload, payload)
        write_json_atomic(args.analysis, analysis)
        print(json.dumps(analysis, indent=2, sort_keys=True))
        return 0
    if args.command == "tables":
        result = build_research_tables(args.results, args.output)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "compute-budget":
        fps: dict[int, float] = {}
        for raw in args.fps:
            left, separator, right = raw.partition("=")
            if not separator:
                raise ValueError("--fps entries require N_ENVS=FPS")
            fps[int(left)] = float(right)
        result = build_compute_budget(
            decisions_per_full_path=args.decisions_per_full_path,
            wf_decisions_per_full_path=args.wf_decisions_per_full_path,
            n_envs_values=args.n_envs,
            rollout_steps_per_env=args.rollout_steps_per_env,
            batch_size=args.batch_size,
            epochs=args.epochs,
            supplied_total_timesteps=args.supplied_total_timesteps,
            fps_by_n_envs=fps or None,
        )
        from artifacts.atomic import write_json_atomic

        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    manifest = assemble_release(
        consolidated_results=args.results,
        protocol=args.protocol,
        catalog=args.catalog,
        output_dir=args.output,
        extra_artifacts=tuple(args.extra),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
