from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest


def _load_try24_runner() -> Any:
    repository = Path(__file__).resolve().parents[3]
    runner_path = (
        repository
        / "logs/agents/quantitative_trading_engineer/20261120_task13_source_tick_closure_try24/run_source_tick_cases.py"
    )
    if not runner_path.exists():
        pytest.skip(
            f"Task 13 evidence runner is an ignored log artifact, absent here: {runner_path}"
        )
    spec = importlib.util.spec_from_file_location("task13_try24_hard_breach_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load Task 13 runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hard_breach_account_trace_uses_source_fill_timestamp(tmp_path: Path) -> None:
    runner = _load_try24_runner()
    runner.HERE = tmp_path

    report = runner.run_hard_breach(
        runner.load_helpers(), runner.source_fingerprint()["combined_sha256"]
    )

    mismatches = [
        row
        for row in report["account_state_parity"]["rows"]
        if "valuation_time" in row["mismatches"]
    ]
    assert not mismatches, mismatches


def test_hard_breach_latch_blocks_post_breach_reentry_in_both_engines(tmp_path: Path) -> None:
    runner = _load_try24_runner()
    runner.HERE = tmp_path

    report = runner.run_hard_breach(
        runner.load_helpers(), runner.source_fingerprint()["combined_sha256"]
    )

    audit = report["daily_loss_latch_audit"]
    assert audit["reentry_attempted_after_latch"] is True
    assert audit["environment_reentry_blocked"] is True
    assert audit["backtest_reentry_blocked"] is True
    assert audit["backtest_reentry_suppressed_by_latch"] is True
