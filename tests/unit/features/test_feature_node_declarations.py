"""Registry node declarations: every output has a unit, every node has a validity policy.

Uses the configured ``features`` node only; no bars are read.
"""

from __future__ import annotations

import pytest
from omegaconf import DictConfig

from configuration.configuration_loader import load_config
from features.graph import UNITS, VALIDITY_POLICIES
from features.registry import registry_nodes


@pytest.fixture(scope="module")
def nodes() -> list:
    cfg: DictConfig = load_config()
    return registry_nodes(cfg.features)


def test_every_output_declares_a_unit_from_the_closed_vocabulary(nodes) -> None:
    for node in nodes:
        for column in node.outputs:
            assert column.units in UNITS, (node.node_id, column.name)


def test_every_node_declares_a_validity_policy_from_the_closed_vocabulary(nodes) -> None:
    for node in nodes:
        assert node.validity in VALIDITY_POLICIES, node.node_id


def test_previous_day_levels_are_valid_after_the_first_day_not_after_a_bar_count(nodes) -> None:
    by_id = {node.node_id: node for node in nodes}
    assert by_id["M1.prev_day_range"].validity == "finite_after_prior_day"
    assert by_id["M1.prev_day_range"].warmup_bars == 0
    assert by_id["M1.ema"].validity == "finite_after_warmup"


def test_units_follow_the_computation_for_representative_outputs(nodes) -> None:
    units = {c.name: c.units for node in nodes if node.timeframe == "M1" for c in node.outputs}
    assert units["ema_9"] == "price"
    assert units["ema_9_slope"] == "price_per_bar"
    assert units["ema_9_dist"] == "ratio"
    assert units["rsi"] == "percent"
    assert units["ret_1"] == "log_return"
    assert units["realized_vol"] == "log_return_stdev"
    assert units["atr_norm_price"] == "atr_multiple"
    assert units["hh"] == "flag"
    assert units["last_swing_side"] == "direction"
    assert units["ny_minutes_to_close"] == "unit_interval"
