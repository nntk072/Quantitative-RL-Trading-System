from __future__ import annotations

import json
from pathlib import Path

from scripts.research.benchmarks.summarize_compact_observation_transport import summarize


def _case(seed: int, *, compact: bool) -> dict[str, object]:
    return {
        "config_sha256": "config-hash",
        "bundle_manifest_sha256": "bundle-hash",
        "n_envs": 64,
        "effective_ppo_n_steps_per_env": 256,
        "batch_size": 4096,
        "ppo_epochs_completed": 15,
        "actual_env_steps": 81920,
        "compact_observation_transport": compact,
        "measured_ppo_core_steps_per_second": (1000.0 + seed if not compact else 1300.0 + seed),
        "rollout_steps_per_second": 5000.0 if not compact else 5001.0,
        "ipc_transport": {"recv_bytes": 1000000 if not compact else 250000},
    }


def test_summarizer_reports_matched_transport_and_speed_results(tmp_path: Path) -> None:
    for seed in (42, 43, 44):
        for mode, compact in (("stock", False), ("compact", True)):
            path = tmp_path / f"{mode}-seed{seed}.json"
            path.write_text(json.dumps(_case(seed, compact=compact)), encoding="utf-8")
    (tmp_path / "validation2.json").write_text(
        json.dumps({"compact_market_validation": True}), encoding="utf-8"
    )

    report = summarize(tmp_path)

    assert "market hashes: PASS" in report
    assert "- >=20% repeatable PPO-core speedup gate: PASS." in report
    assert "75.00%" in report
