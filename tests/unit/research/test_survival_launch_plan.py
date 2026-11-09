from pathlib import Path

from scripts.research.analysis.evidence.build_survival_launch_plan import build_launch_plan

from training.configuration.research_protocol import load_research_protocol

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def test_launch_plan_freezes_six_seeds_and_walk_forward_without_executing() -> None:
    plan = build_launch_plan(load_research_protocol(PROTOCOL), "outputs/test-survival")
    assert plan["executes_commands"] is False
    assert plan["allocates_compute"] is False
    assert plan["portfolio_phase_command"] is None
    assert plan["portfolio_phase_blocked_until_survival_gate"] is True
    assert len(plan["qualification_commands"]) == 3
    canonical = next(row for row in plan["qualification_commands"] if row["role"] == "canonical")
    argv = canonical["command_argv"]
    seeds_at = argv.index("--seeds") + 1
    wf_at = argv.index("--walk-forward")
    assert argv[seeds_at:wf_at] == ["42", "43", "44", "45", "46", "47"]
    assert argv[argv.index("--wf-splits") + 1] == "5"
    assert argv[argv.index("--purge-bars") + 1] == "60"
    assert argv[argv.index("--embargo-bars") + 1] == "20"
    price = next(row for row in plan["qualification_commands"] if row["role"] == "price_geometry")
    assert price["authorized_before_candidate_acceptance"] is False
