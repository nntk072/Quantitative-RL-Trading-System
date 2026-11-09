from scripts.research.benchmarks.build_v3_compute_contract import build_compute_contract


def test_compute_contract_scales_steps_with_n_envs_and_wf_terminal_exposure() -> None:
    payload = build_compute_contract(
        decisions_per_full_path=100_000,
        wf_decisions_per_full_path=[80_000] * 5,
        n_envs_values=[8, 16],
        rollout_steps_per_env=256,
        batch_size=2048,
        epochs=10,
        minimum_full_paths_per_env=2.0,
        supplied_total_timesteps=2_000_000,
        fps_by_n_envs={8: 1000.0, 16: 1200.0},
        seed_count=6,
        wf_split_count=5,
        allocation_hours=12.0,
    )
    rows = {row["n_envs"]: row for row in payload["rows"]}
    assert rows[8]["main_full_paths_per_env"] >= 2.0
    assert (
        rows[16]["main_rounded_aggregate_timesteps"] > rows[8]["main_rounded_aggregate_timesteps"]
    )
    assert all(row["full_paths_per_env"] >= 2.0 for row in rows[8]["walk_forward"])
