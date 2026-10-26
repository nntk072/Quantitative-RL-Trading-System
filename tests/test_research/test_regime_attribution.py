from __future__ import annotations

import numpy as np
import pandas as pd
from scripts.research.thesis.regime_attribution import (
    _decision_intent_summary,
    attach_completed_context,
    build_completed_daily_context,
)


def _daily_bars() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=12, freq="D", tz="Etc/GMT-3")
    close = np.array([100.0 + day for day in range(len(index))])
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        },
        index=index,
    )


def test_daily_context_is_unavailable_until_the_bar_close() -> None:
    daily = _daily_bars()
    context = build_completed_daily_context(daily)
    decisions = pd.Series(
        pd.to_datetime(["2025-01-01 12:00:00+03:00", "2025-01-02 12:00:00+03:00"], utc=True)
    )

    joined = attach_completed_context(decisions, context)

    assert pd.isna(joined.loc[0, "available_at"])
    assert pd.Timestamp(joined.loc[1, "available_at"]) == pd.Timestamp("2025-01-01 21:00:00+00:00")


def test_daily_context_does_not_change_when_future_bars_change() -> None:
    daily = _daily_bars()
    modified = daily.copy()
    modified.loc["2025-01-10":, ["open", "high", "low", "close"]] *= 4.0
    decision = pd.Series(pd.to_datetime(["2025-01-10 12:00:00+03:00"], utc=True))

    original_state = attach_completed_context(decision, build_completed_daily_context(daily))
    modified_state = attach_completed_context(decision, build_completed_daily_context(modified))

    assert original_state.loc[0, "available_at"] == modified_state.loc[0, "available_at"]
    assert original_state.loc[0, "ret_5d"] == modified_state.loc[0, "ret_5d"]
    assert original_state.loc[0, "trend_regime"] == modified_state.loc[0, "trend_regime"]


def test_decision_intent_summary_counts_logged_open_and_reject_rows() -> None:
    events = pd.DataFrame(
        {
            "type": ["open", "reject", "close"],
            "decision_time": ["2025-01-02T10:00:00Z", None, "2025-01-02T11:00:00Z"],
            "time": [None, "2025-01-03T10:00:00Z", None],
            "action_direction": [1.0, -1.0, 1.0],
            "action_intensity": [0.8, 0.4, 0.2],
            "action_risk": [0.5, 0.2, 0.9],
        }
    )

    result = _decision_intent_summary(events)

    assert result["month"].tolist() == ["2025-01"]
    assert result.loc[0, "logged_entry_intents"] == 2
    assert result.loc[0, "opened"] == 1
    assert result.loc[0, "rejected"] == 1
    assert result.loc[0, "open_event_share"] == 0.5
