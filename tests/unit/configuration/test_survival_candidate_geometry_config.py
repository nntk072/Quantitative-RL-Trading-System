from __future__ import annotations

from configuration import load_config
from configuration.paths import repository_root


def test_survival_price_overlay_resolves_candidate_geometry_contract() -> None:
    root = repository_root(__file__)
    cfg = load_config(
        config_path=root / "config" / "research" / "survival_trade_setup_candidate_geometry.yaml"
    )

    assert cfg.env.reward_mode == "survival"
    assert cfg.env.strategy_actions is True
    assert cfg.env.trade_setup_actions is True
    assert cfg.env.candidate_geometry_actions is True
    assert cfg.env.agent_entry_execution is True
    assert cfg.ppo.policy_distribution == "trade_setup_candidate_geometry_v1"
    assert float(cfg.ppo.gamma) == 1.0
    assert float(cfg.ppo.gae_lambda) == 1.0
    assert int(cfg.env.n_envs) == 8
    assert list(cfg.data.timeframes) == ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"]
    assert list(cfg.features.entry_ideas.timeframes) == [
        "M1",
        "M3",
        "M5",
        "M10",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
    ]


def test_survival_c_and_d_overlays_keep_price_geometry_disabled() -> None:
    root = repository_root(__file__)
    for filename, distribution in (
        ("survival_trade_setup_mtf_control.yaml", "trade_setup_hybrid_v1"),
        ("survival_trade_setup_mtf_conditioned.yaml", "trade_setup_conditioned_v1"),
    ):
        cfg = load_config(config_path=root / "config" / "research" / filename)
        assert cfg.env.candidate_geometry_actions is False
        assert cfg.env.agent_entry_execution is False
        assert cfg.ppo.policy_distribution == distribution
        assert cfg.env.reward_mode == "survival"
