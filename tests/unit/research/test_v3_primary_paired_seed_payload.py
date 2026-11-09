import hashlib
from pathlib import Path

from scripts.research.analysis.evidence.build_v3_primary_paired_seed_payload import build_payload


def test_primary_payload_builds_exact_six_seed_v2_contract(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    pairs = []
    for seed in range(42, 48):
        common = {
            "dataset_sha256": "a" * 64,
            "split_id": "development",
            "features_sha256": "b" * 64,
            "reward_sha256": "c" * 64,
            "costs_sha256": "d" * 64,
            "execution_sha256": "e" * 64,
            "timesteps": 2_000_000,
            "seed": seed,
            "initial_capital": 100_000.0,
            "model_settings_sha256": "f" * 64,
            "environment_sha256": "1" * 64,
            "evaluation_start": "2024-12-30T00:00:00Z",
            "evaluation_end": "2025-12-31T23:59:00Z",
        }
        source_artifacts = [{"path": str(source), "sha256": digest}]
        control = {
            "run_id": f"control-{seed}",
            "policy_id": "always_no_trade_v1",
            "evaluation_complete": True,
            "hard_risk_gate_passed": True,
            "initial_operating_equity": 100_000.0,
            "ending_retained_equity": 100_000.0,
            "cumulative_payouts": 0.0,
            "trade_count": 0,
            "net_return_initial_equity_pct": 0.0,
            "provenance": {**common, "policy_sha256": "2" * 64},
            "source_artifacts": source_artifacts,
        }
        treatment = {
            "run_id": f"treatment-{seed}",
            "policy_id": "qualified_policy_v1",
            "evaluation_complete": True,
            "hard_risk_gate_passed": True,
            "initial_operating_equity": 100_000.0,
            "ending_retained_equity": 101_000.0,
            "cumulative_payouts": 0.0,
            "trade_count": 5,
            "net_return_initial_equity_pct": 1.0,
            "provenance": {**common, "policy_sha256": "3" * 64},
            "source_artifacts": source_artifacts,
        }
        pairs.append({"seed": seed, "control": control, "treatment": treatment})
    payload = build_payload(
        {
            "schema_version": "v3-primary-pair-sources-v1",
            "comparison_id": "primary",
            "evaluation_exposure": "development",
            "expected_seeds": list(range(42, 48)),
            "pairs": pairs,
        }
    )
    assert payload["schema"] == "aalto.paired_seed_metrics.v2"
    assert payload["expected_seeds"] == list(range(42, 48))
    assert len(payload["pairs"]) == 6
