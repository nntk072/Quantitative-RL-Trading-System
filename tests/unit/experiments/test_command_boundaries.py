"""Stable experiment CLI parsing and package dispatch contracts."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from scripts.research.benchmarks import compare_encoders

from experiments import cli
from experiments.variants.variant_ablation_runner import (
    VariantAblationRequest,
    run_variant_ablation,
    train_and_score_variant,
)


def test_variant_arguments_resolve_into_runner_request() -> None:
    request = cli.parse_variant_ablation_args(
        [
            "--bars-csv",
            "bars.csv",
            "--features-csv",
            "features.csv",
            "--steps",
            "128",
            "--seeds",
            "7",
            "9",
            "--variants",
            "baseline",
            "treatment",
            "--out-dir",
            "outputs/ablation-test",
        ]
    )

    assert isinstance(request, VariantAblationRequest)
    assert request.bars_csv.as_posix() == "bars.csv"
    assert request.features_csv is not None
    assert request.features_csv.as_posix() == "features.csv"
    assert request.steps == 128
    assert request.seeds == (7, 9)
    assert request.variants == ("baseline", "treatment")


def test_legacy_variant_training_entry_points_fail_closed(tmp_path: Path) -> None:
    request = VariantAblationRequest(bars_csv=tmp_path / "missing-bars.csv")
    with pytest.raises(SystemExit, match="bypasses survival-first qualification"):
        run_variant_ablation(request)

    with pytest.raises(SystemExit, match="bypasses survival-first qualification"):
        train_and_score_variant(
            bars=cast(Any, None),
            features=cast(Any, None),
            base_cfg=cast(Any, None),
            variant={},
            defaults={},
            steps=100,
            seed=42,
            reward="dsr",
            train_end="2025-12-31",
            test_start="2026-01-01",
            out_dir=str(tmp_path),
            name="unqualified",
        )


@pytest.mark.parametrize(
    "argv",
    [
        ["compare_encoders.py"],
        ["compare_encoders.py", "--bars-csv", "unread-bars.csv"],
    ],
)
def test_direct_encoder_comparison_training_fails_closed(monkeypatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit, match="bypasses survival-first qualification"):
        compare_encoders.main()


def test_root_variants_command_forwards_arguments_at_package_boundary(monkeypatch) -> None:
    captured: list[list[str]] = []

    def capture(argv: list[str]) -> None:
        captured.append(list(argv))

    monkeypatch.setattr(cli, "run_variant_ablation_cli", capture)
    monkeypatch.setattr(
        sys,
        "argv",
        ["qrl-experiment", "variants", "--bars-csv", "bars.csv", "--steps", "64"],
    )

    cli.main()

    assert captured == [["--bars-csv", "bars.csv", "--steps", "64"]]


def test_root_catalog_command_forwards_generation_mode(monkeypatch) -> None:
    captured: list[list[str]] = []

    def capture(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(cli, "run_variant_catalog_cli", capture)
    monkeypatch.setattr(sys, "argv", ["qrl-experiment", "catalog", "--check"])

    cli.main()

    assert captured == [["--check"]]


def test_named_cache_plan_command_dispatches_without_rebuild(monkeypatch, capsys) -> None:
    from experiments.runs import named_cache_rebuild

    monkeypatch.setattr(named_cache_rebuild, "plan", lambda: [{"target": "cache/example.parquet"}])

    assert cli.run_named_cache_rebuild_cli(["--plan-only"]) == 0
    assert '"status": "plan_only"' in capsys.readouterr().out


def test_root_named_cache_command_forwards_to_stable_parser(monkeypatch) -> None:
    captured: list[list[str]] = []

    def capture(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(cli, "run_named_cache_rebuild_cli", capture)
    monkeypatch.setattr(sys, "argv", ["qrl-experiment", "rebuild-named-cache", "--plan-only"])

    cli.main()

    assert captured == [["--plan-only"]]


def test_legacy_named_cache_module_forwards_to_stable_parser(monkeypatch) -> None:
    from experiments.runs import named_cache_rebuild

    captured: list[list[str]] = []

    def capture(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(cli, "run_named_cache_rebuild_cli", capture)
    monkeypatch.setattr(sys, "argv", ["named_cache_rebuild", "--plan-only"])

    assert named_cache_rebuild.main() == 0
    assert captured == [["--plan-only"]]


@pytest.mark.parametrize(
    ("command", "module_name", "attribute"),
    [
        ("run", "experiments.runs", "run_experiment"),
        ("status", "experiments.runs.status", "main"),
        ("summarize", "experiments.runs.reporting", "main"),
        ("checkpoint-map", "experiments.runs.checkpoints", "main"),
        ("recover-cache", "experiments.runs.cache_failure_recovery", "main"),
    ],
)
def test_main_forwards_each_run_command_with_original_argv_restored(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    module_name: str,
    attribute: str,
) -> None:
    seen: list[list[str]] = []
    module = ModuleType(module_name)

    def command_main() -> None:
        seen.append(sys.argv[1:])

    setattr(module, attribute, command_main)
    if module_name == "experiments.runs":
        import experiments.runs

        monkeypatch.setattr(experiments.runs, attribute, command_main)
    else:
        import experiments.runs

        monkeypatch.setitem(sys.modules, module_name, module)
        monkeypatch.setattr(
            experiments.runs,
            module_name.rsplit(".", maxsplit=1)[-1],
            module,
            raising=False,
        )
    argv = ["qrl-experiment", command, "--sample", "value"]
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    assert seen == [["--sample", "value"]]
    assert sys.argv == argv


def test_main_propagates_nonzero_run_exit_and_restores_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import experiments.runs

    monkeypatch.setattr(experiments.runs, "run_experiment", lambda: 2)
    argv = ["qrl-experiment", "run"]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit, match="2"):
        cli.main()

    assert sys.argv == argv


def test_root_catalog_command_propagates_nonzero_catalog_status(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_variant_catalog_cli", lambda _argv: 5)
    monkeypatch.setattr(sys, "argv", ["qrl-experiment", "catalog", "--check"])

    with pytest.raises(SystemExit, match="5"):
        cli.main()


def test_variant_catalog_cli_passes_explicit_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    from experiments.variants import catalog as variant_catalog

    calls: list[list[str] | None] = []

    def catalog_main(argv: list[str] | None) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr(variant_catalog, "main", catalog_main)

    assert cli.run_variant_catalog_cli(["--check"]) == 0
    assert calls == [["--check"]]


def test_run_named_cache_command_resolves_relative_paths_and_prints_result(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from experiments.runs import named_cache_rebuild

    calls: list[tuple[Path, Path]] = []

    def rebuild(backup: Path, report: Path) -> dict[str, str]:
        calls.append((backup, report))
        return {"status": "complete"}

    monkeypatch.setattr(named_cache_rebuild, "rebuild", rebuild)

    assert (
        cli.run_named_cache_rebuild_cli(["--backup-dir", "backup", "--report", "report.json"]) == 0
    )

    root = Path(cli.__file__).resolve().parents[1]
    assert calls == [(root / "backup", root / "report.json")]
    assert '"status": "complete"' in capsys.readouterr().out


def test_run_variant_ablation_cli_delegates_parsed_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from experiments.variants import variant_ablation_runner

    captured: list[VariantAblationRequest] = []
    monkeypatch.setattr(
        variant_ablation_runner,
        "run_variant_ablation",
        lambda request: captured.append(request),
    )

    cli.run_variant_ablation_cli(["--bars-csv", "bars.csv", "--features-csv", "features.csv"])

    assert len(captured) == 1
    assert captured[0].bars_csv == Path("bars.csv")
    assert captured[0].features_csv == Path("features.csv")
