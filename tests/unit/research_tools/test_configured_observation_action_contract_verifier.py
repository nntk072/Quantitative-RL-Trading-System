from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WRAPPER = (
    ROOT / "scripts/research/analysis/models/verify_configured_observation_action_contracts.py"
)


def test_verifier_cli_help_does_not_require_evidence_files() -> None:
    result = subprocess.run(
        [sys.executable, str(WRAPPER), "--help"],
        cwd=ROOT.parent,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "--control-contract" in result.stdout
    assert "--conditioned-contract" in result.stdout
    assert "--support-review" in result.stdout
    assert "--trace-inventory" in result.stdout
    assert "--output-dir" in result.stdout


def test_builder_source_manifest_hashes_the_report_implementation() -> None:
    import hashlib

    from research_tools.decisioning.models.build_configured_observation_action_contract import (
        _implementation_sources,
    )

    implementation = (
        ROOT / "research_tools/decisioning/models/build_configured_observation_action_contract.py"
    )
    sources = {item["path"]: item["sha256"] for item in _implementation_sources(ROOT)}

    assert implementation.relative_to(ROOT).as_posix() in sources
    assert (
        sources[implementation.relative_to(ROOT).as_posix()]
        == hashlib.sha256(implementation.read_bytes()).hexdigest()
    )


def _build_valid_inputs(directory: Path) -> dict[str, Path]:
    import csv
    import hashlib
    import json

    source = (
        ROOT / "research_tools/decisioning/models/build_configured_observation_action_contract.py"
    )
    test_source = ROOT / "tests/unit/models/test_encoders.py"

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    identity = {
        "implementation_sources": [
            {"path": source.relative_to(ROOT).as_posix(), "sha256": digest(source)}
        ],
        "source_files": [
            {
                "path": test_source.relative_to(ROOT).as_posix(),
                "role": "fixture",
                "sha256": digest(test_source),
            }
        ],
        "resolved_config_sha256": "config-hash",
        "dataset_records": {"training": 10},
    }
    base_report = {
        "identity": identity,
        "observation": {"reset_output_shapes": {"trade_setup_mask": [109], "market": [32]}},
        "action": {"schema": {"trade_setup_category_count": 109, "coordinates": 6}},
        "scope": {
            "config": "fixture.yaml",
            "environment_steps": 0,
            "policy_actions": 0,
            "report_period_rows_used": 0,
            "trades_or_economics": False,
            "train_start": "2020-01-01",
            "train_end": "2020-01-31",
        },
        "policy_configuration": {"setup_conditioned_execution": False},
    }
    control = directory / "control.json"
    conditioned = directory / "conditioned.json"
    control.write_text(json.dumps(base_report), encoding="utf-8")
    conditioned_report = json.loads(json.dumps(base_report))
    conditioned_report["policy_configuration"]["setup_conditioned_execution"] = True
    conditioned.write_text(json.dumps(conditioned_report), encoding="utf-8")

    support = directory / "support.csv"
    with support.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["support_review_status", "family_enabled_by_audit_config"]
        )
        writer.writeheader()
        writer.writerows(
            {
                "support_review_status": "supported",
                "family_enabled_by_audit_config": str(index < 24),
            }
            for index in range(108)
        )

    trace = directory / "trace.json"
    trace.write_text(json.dumps({"artifact_count": 0, "artifacts": []}), encoding="utf-8")
    return {
        "--control-contract": control,
        "--conditioned-contract": conditioned,
        "--support-review": support,
        "--trace-inventory": trace,
    }


def _run_verifier(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), *arguments],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )


def test_verifier_accepts_cwd_relative_inputs_and_external_output(tmp_path: Path) -> None:
    import json

    invocation = tmp_path / "invocation"
    inputs = invocation / "evidence"
    inputs.mkdir(parents=True)
    paths = _build_valid_inputs(inputs)
    output_dir = tmp_path / "external-output"
    arguments = [
        value
        for index, (flag, path) in enumerate(paths.items())
        for value in (flag, str(path.relative_to(invocation)) if index % 2 == 0 else str(path))
    ]

    result = _run_verifier([*arguments, "--output-dir", str(output_dir)], invocation)

    assert result.returncode == 0, result.stderr
    report = json.loads((output_dir / "verification.json").read_text(encoding="utf-8"))
    assert report["candidate_support"]["input_path"] == str(paths["--support-review"])
    assert report["trace_inventory"]["path"] == str(paths["--trace-inventory"])
    assert (output_dir / "README.md").is_file()
    assert (output_dir / "SHA256SUMS").is_file()


@pytest.mark.parametrize(
    ("missing_flag", "missing_name"),
    [
        ("--control-contract", "control.json"),
        ("--conditioned-contract", "conditioned.json"),
        ("--support-review", "support.csv"),
        ("--trace-inventory", "trace.json"),
    ],
)
def test_verifier_rejects_each_missing_input_before_processing(
    tmp_path: Path, missing_flag: str, missing_name: str
) -> None:
    invocation = tmp_path / "invocation"
    evidence = invocation / "evidence"
    evidence.mkdir(parents=True)
    paths = _build_valid_inputs(evidence)
    paths[missing_flag].unlink()
    arguments = [
        value for flag, path in paths.items() for value in (flag, str(path.relative_to(invocation)))
    ]

    result = _run_verifier([*arguments, "--output-dir", str(tmp_path / "out")], invocation)

    assert result.returncode != 0
    assert missing_name in result.stderr
    assert "required input does not exist" in result.stderr


@pytest.mark.parametrize(
    ("mismatch", "message"),
    [
        ("action_schema", "Matched control and conditioned action schemas differ"),
        ("observation_shapes", "Matched control and conditioned observation shapes differ"),
        ("training_window", "Matched control and conditioned training windows differ"),
        ("dataset_records", "Matched control and conditioned processed datasets differ"),
        ("control_flag", "Control unexpectedly conditions execution on setup ID"),
        ("conditioned_flag", "Conditioned variant does not condition execution on setup ID"),
    ],
)
def test_verifier_rejects_unmatched_contracts_without_changing_checks(
    tmp_path: Path, mismatch: str, message: str
) -> None:
    import json

    invocation = tmp_path / "invocation"
    evidence = invocation / "evidence"
    evidence.mkdir(parents=True)
    paths = _build_valid_inputs(evidence)
    control_path = paths["--control-contract"]
    conditioned_path = paths["--conditioned-contract"]
    report_path = control_path if mismatch == "control_flag" else conditioned_path
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if mismatch == "action_schema":
        report["action"]["schema"]["coordinates"] = 5
    elif mismatch == "observation_shapes":
        report["observation"]["reset_output_shapes"]["market"] = [33]
    elif mismatch == "training_window":
        report["scope"]["train_end"] = "2020-02-01"
    elif mismatch == "dataset_records":
        report["identity"]["dataset_records"] = {"training": 11}
    elif mismatch == "control_flag":
        report["policy_configuration"]["setup_conditioned_execution"] = True
    elif mismatch == "conditioned_flag":
        report["policy_configuration"]["setup_conditioned_execution"] = False
    report_path.write_text(json.dumps(report), encoding="utf-8")
    arguments = [value for flag, path in paths.items() for value in (flag, str(path))]

    result = _run_verifier([*arguments, "--output-dir", str(tmp_path / "out")], invocation)

    assert result.returncode != 0
    assert message in result.stderr


def test_verifier_reports_current_trace_inventory_without_a_fixed_count(
    tmp_path: Path,
) -> None:
    import json

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    paths = _build_valid_inputs(evidence)
    trace_path = paths["--trace-inventory"]
    trace_path.write_text(
        json.dumps(
            {
                "artifact_count": 1,
                "roots": ["registered-run-artifacts"],
                "artifacts": [
                    {
                        "path": "baseline/decisions.csv",
                        "per_decision_setup_trace": True,
                        "per_decision_price_geometry_trace": False,
                    }
                ],
                "per_decision_setup_trace_paths": ["baseline/decisions.csv::file_rows"],
                "per_decision_price_geometry_trace_paths": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "verification"
    arguments = [value for flag, path in paths.items() for value in (flag, str(path))]

    result = _run_verifier([*arguments, "--output-dir", str(output)], tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads((output / "verification.json").read_text(encoding="utf-8"))
    inventory = report["trace_inventory"]
    assert inventory["scanned_artifacts"] == 1
    assert inventory["qualifying_setup_decision_trace"] is True
    assert inventory["qualifying_price_geometry_trace"] is False
    assert inventory["setup_trace_paths"] == ["baseline/decisions.csv::file_rows"]
