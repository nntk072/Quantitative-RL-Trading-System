"""Stable experiment CLI parsing and package dispatch contracts."""

from __future__ import annotations

import sys

from experiments import cli
from experiments.variants.variant_ablation_runner import VariantAblationRequest


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


def test_root_variants_command_forwards_arguments_at_package_boundary(monkeypatch) -> None:
    captured: list[list[str]] = []

    def capture(argv: list[str]) -> None:
        captured.append(list(argv))

    monkeypatch.setattr(cli, "run_variant_ablation_cli", capture)
    monkeypatch.setattr(
        sys,
        "argv",
        ["thesis-campaign", "variants", "--bars-csv", "bars.csv", "--steps", "64"],
    )

    cli.main()

    assert captured == [["--bars-csv", "bars.csv", "--steps", "64"]]


def test_named_cache_plan_command_dispatches_without_rebuild(monkeypatch, capsys) -> None:
    from experiments.campaigns import named_cache_rebuild

    monkeypatch.setattr(named_cache_rebuild, "plan", lambda: [{"target": "cache/example.parquet"}])

    assert cli.run_named_cache_rebuild_cli(["--plan-only"]) == 0
    assert '"status": "plan_only"' in capsys.readouterr().out


def test_root_named_cache_command_forwards_to_stable_parser(monkeypatch) -> None:
    captured: list[list[str]] = []

    def capture(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(cli, "run_named_cache_rebuild_cli", capture)
    monkeypatch.setattr(sys, "argv", ["thesis-campaign", "rebuild-named-cache", "--plan-only"])

    cli.main()

    assert captured == [["--plan-only"]]


def test_legacy_named_cache_module_forwards_to_stable_parser(monkeypatch) -> None:
    from experiments.campaigns import named_cache_rebuild

    captured: list[list[str]] = []

    def capture(argv: list[str]) -> int:
        captured.append(list(argv))
        return 0

    monkeypatch.setattr(cli, "run_named_cache_rebuild_cli", capture)
    monkeypatch.setattr(sys, "argv", ["named_cache_rebuild", "--plan-only"])

    assert named_cache_rebuild.main() == 0
    assert captured == [["--plan-only"]]
