from pathlib import Path

from scripts.research.audits.verify_pretraining_research_contract import verify

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = ROOT / "config/research/prospective_research_protocol.yaml"


def test_static_pretraining_contract_gate_passes_repository_configs() -> None:
    report = verify(PROTOCOL)
    assert report["status"] == "pass"
    assert report["failures"] == []
    assert "full_tree_ci" in report["does_not_establish"]
    assert "survival_qualification" in report["does_not_establish"]
