from scripts.research.benchmarks.plan_survival_compute_budget import (
    build_budget_table,
    full_path_equivalents_per_env,
    minimum_aggregate_timesteps,
)


def test_full_path_math_exposes_large_n_envs_terminal_signal_problem() -> None:
    decisions = 99492
    assert (
        full_path_equivalents_per_env(2_000_000, n_envs=8, decisions_per_full_path=decisions) > 2.0
    )
    assert (
        full_path_equivalents_per_env(2_000_000, n_envs=64, decisions_per_full_path=decisions)
        < 0.32
    )


def test_matched_budget_scales_with_environment_count() -> None:
    decisions = 99492
    eight = minimum_aggregate_timesteps(
        n_envs=8,
        decisions_per_full_path=decisions,
        minimum_full_paths_per_env=2.0,
    )
    sixty_four = minimum_aggregate_timesteps(
        n_envs=64,
        decisions_per_full_path=decisions,
        minimum_full_paths_per_env=2.0,
    )
    assert eight == 1_591_872
    assert sixty_four == eight * 8


def test_budget_table_reports_semantic_sufficiency_and_wall_time() -> None:
    rows = build_budget_table(
        decisions_per_full_path=100,
        n_envs_values=[1, 8],
        minimum_full_paths_per_env=2.0,
        supplied_aggregate_timesteps=1000,
        fps_by_n_envs={1: 100.0, 8: 400.0},
    )
    assert rows[0].supplied_budget_is_semantically_sufficient is True
    assert rows[1].supplied_budget_is_semantically_sufficient is False
    assert rows[0].estimated_wall_seconds_for_minimum == 2.0
    assert rows[1].estimated_wall_seconds_for_minimum == 4.0
