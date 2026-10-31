"""Stable experiment and experiment run command surface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.variants.variant_ablation_runner import VariantAblationRequest


def _cli_program() -> str:
    """Return the actual installed entrypoint name, defaulting to the canonical name."""
    program = Path(sys.argv[0]).name
    return program if program not in {"pytest", "-c"} else "qrl-experiment"


def _forward(callable_main: Callable[[], object], argv: list[str]) -> None:
    original = sys.argv
    try:
        sys.argv = [original[0], *argv]
        result = callable_main()
        if isinstance(result, int) and result:
            raise SystemExit(result)
    finally:
        sys.argv = original


def parse_variant_ablation_args(
    argv: Sequence[str] | None = None,
) -> VariantAblationRequest:
    """Parse the legacy ablation command at the stable CLI boundary."""
    from experiments.variants.variant_ablation_runner import VariantAblationRequest

    parser = argparse.ArgumentParser(
        prog=f"{_cli_program()} variants",
        description="Run the configured ablation workflow.",
    )
    parser.add_argument("--bars-csv", required=True, help="OHLCV CSV with DatetimeIndex")
    parser.add_argument(
        "--features-csv",
        help="Feature CSV aligned to bars; defaults to numeric columns of bars",
    )
    parser.add_argument("--rl-config", default=None, help="Base RL config (default.yaml)")
    parser.add_argument("--experiments", default="config/experiments.yaml")
    parser.add_argument("--steps", type=int, default=None, help="Override per-variant steps")
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=None,
        help="Override seed list (default: experiments.yaml defaults.seeds)",
    )
    parser.add_argument("--variants", nargs="+", default=None, help="Optional variant subset")
    parser.add_argument("--reward", choices=["dsr", "sweep"], default="dsr")
    parser.add_argument("--out-dir", default="outputs/ablations")
    parser.add_argument(
        "--allow-locked-oos-for-selection",
        action="store_true",
        help=(
            "Acknowledge that locked OOS scores may be used for ranking variants. "
            "Default treats OOS as final_report_only (T-03.2)."
        ),
    )
    args = parser.parse_args(argv)
    return VariantAblationRequest(
        bars_csv=Path(args.bars_csv),
        experiments=Path(args.experiments),
        features_csv=Path(args.features_csv) if args.features_csv else None,
        rl_config=args.rl_config,
        steps=args.steps,
        seeds=tuple(args.seeds) if args.seeds is not None else None,
        variants=tuple(args.variants) if args.variants is not None else None,
        reward=args.reward,
        out_dir=Path(args.out_dir),
        allow_locked_oos_for_selection=args.allow_locked_oos_for_selection,
    )


def run_variant_ablation_cli(argv: Sequence[str] | None = None) -> None:
    """Run the variant ablation through its stable package API."""
    from experiments.variants.variant_ablation_runner import run_variant_ablation

    run_variant_ablation(parse_variant_ablation_args(argv))


def run_named_cache_rebuild_cli(argv: Sequence[str] | None = None) -> int:
    """Parse and dispatch the named-cache transaction command."""
    parser = argparse.ArgumentParser(
        prog=f"{_cli_program()} rebuild-named-cache",
        description="Stage, validate, and transactionally publish named feature caches.",
    )
    parser.add_argument("--plan-only", action="store_true", help="resolve paths without writing")
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    from experiments.runs.named_cache_rebuild import plan, rebuild

    if args.plan_only:
        print(json.dumps({"status": "plan_only", "caches": plan()}, indent=2))
        return 0
    if args.backup_dir is None or args.report is None:
        parser.error("--backup-dir and --report are required unless --plan-only is used")
    root = Path(__file__).resolve().parents[1]
    report_path = (args.report if args.report.is_absolute() else root / args.report).resolve()
    backup_dir = (
        args.backup_dir if args.backup_dir.is_absolute() else root / args.backup_dir
    ).resolve()
    result = rebuild(backup_dir, report_path)
    print(json.dumps(result, indent=2), flush=True)
    return 0


def run_variant_catalog_cli(argv: Sequence[str] | None = None) -> int:
    """Generate or validate the model and experiment variant catalog."""
    from experiments.variants.catalog import main as catalog_main

    return catalog_main(list(argv) if argv is not None else None)


def main() -> None:
    parser = argparse.ArgumentParser(prog=_cli_program())
    parser.add_argument(
        "command",
        choices=(
            "run",
            "status",
            "summarize",
            "checkpoint-map",
            "recover-cache",
            "rebuild-named-cache",
            "variants",
            "catalog",
        ),
    )
    argv = sys.argv[1:]
    args = parser.parse_args(argv[:1])
    rest = argv[1:]
    if args.command == "variants":
        run_variant_ablation_cli(rest)
        return
    if args.command == "rebuild-named-cache":
        run_named_cache_rebuild_cli(rest)
        return
    if args.command == "catalog":
        status = run_variant_catalog_cli(rest)
        if status:
            raise SystemExit(status)
        return

    command_main: Callable[[], object]
    if args.command == "run":
        from experiments.runs import run_experiment as command_main
    elif args.command == "status":
        from experiments.runs.status import main as command_main
    elif args.command == "summarize":
        from experiments.runs.reporting import main as command_main
    elif args.command == "checkpoint-map":
        from experiments.runs.checkpoints import main as command_main
    else:
        from experiments.runs.cache_failure_recovery import main as command_main
    _forward(command_main, rest)
