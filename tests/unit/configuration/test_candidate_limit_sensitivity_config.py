from omegaconf import OmegaConf

from configuration.configuration_loader import load_config
from configuration.paths import repository_root


def test_trade_through_profile_differs_only_by_limit_fill_rule() -> None:
    root = repository_root(__file__)
    exact_touch = load_config(
        config_path=root / "config/research/trade_setup_mtf_reasoning_2m.yaml"
    )
    trade_through = load_config(
        config_path=root / "config/research/candidate_limit_trade_through_sensitivity.yaml"
    )

    assert exact_touch.execution.limit_order_require_trade_through is False
    assert trade_through.execution.limit_order_require_trade_through is True
    trade_through.execution.limit_order_require_trade_through = False
    assert OmegaConf.to_container(trade_through, resolve=True) == OmegaConf.to_container(
        exact_touch, resolve=True
    )
