"""The runtime correctness smoke uses configured synthetic quote data."""

from __future__ import annotations

import pandas as pd
import pytest
from scripts.research.audits.run_survival_correctness_smoke import (
    _build_environment,
    _synthetic_inputs,
    _validate_replay_action_mask,
)

from configuration import load_config
from decisioning.trade_setup import NO_TRADE_ID


def test_smoke_environment_supplies_tick_quotes_for_every_synthetic_bar() -> None:
    cfg = load_config()
    bars, features = _synthetic_inputs()

    env = _build_environment(bars, features, cfg)

    tickbook = env._tickbook
    assert tickbook is not None
    assert len(tickbook._ts) == len(bars)
    assert tickbook._ts[0] == bars.index[0].value
    assert tickbook._ts[-1] == bars.index[-1].value


def test_smoke_requires_legal_masked_actions_and_no_trade_fallback() -> None:
    replay = {
        "n_steps": 2,
        "trade_setup_decisions": pd.DataFrame(
            [
                {
                    "trade_setup_candidate_id": NO_TRADE_ID,
                    "selection_valid": True,
                    "eligible_trade_setup_ids": [NO_TRADE_ID, 2],
                },
                {
                    "trade_setup_candidate_id": 2,
                    "selection_valid": True,
                    "eligible_trade_setup_ids": [NO_TRADE_ID, 2],
                },
            ]
        ),
    }

    assert _validate_replay_action_mask(replay) == 2


def test_smoke_rejects_masked_setup_selection() -> None:
    replay = {
        "n_steps": 1,
        "trade_setup_decisions": pd.DataFrame(
            [
                {
                    "trade_setup_candidate_id": 3,
                    "selection_valid": False,
                    "eligible_trade_setup_ids": [NO_TRADE_ID, 2],
                }
            ]
        ),
    }

    with pytest.raises(RuntimeError, match="ineligible setup"):
        _validate_replay_action_mask(replay)
