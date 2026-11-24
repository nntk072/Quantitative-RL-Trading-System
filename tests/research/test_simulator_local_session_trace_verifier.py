"""Contracts for the independent session-account trace verifier."""

from __future__ import annotations

from research_tools.simulation.evaluation.verify_simulator_local_session_account_trace import (
    _source_code_path_for_hash,
)

from configuration.paths import repository_root


def test_session_trace_verifier_resolves_generator_to_implementation_source() -> None:
    root = repository_root(__file__)

    assert _source_code_path_for_hash("generator") == (
        root
        / "research_tools/simulation/evaluation/compare_simulator_local_session_account_trace.py"
    )
