from __future__ import annotations

import pandas as pd
import pytest
from omegaconf import OmegaConf

from market_data.transforms import scheduled_session_close_map


def test_scheduled_session_close_map_reads_configured_calendar(tmp_path) -> None:
    schedule_path = tmp_path / "session_schedule.csv"
    pd.DataFrame(
        {
            "session_date": ["2025-11-28", "2025-12-24"],
            "scheduled_ny_close_broker_time": ["21:00", "20:00"],
        }
    ).to_csv(schedule_path, index=False)
    cfg = OmegaConf.create({"data": {"session_schedule_file": str(schedule_path)}})

    assert scheduled_session_close_map(cfg) == {
        "2025-11-28": "21:00",
        "2025-12-24": "20:00",
    }


def test_scheduled_session_close_map_rejects_missing_required_columns(tmp_path) -> None:
    schedule_path = tmp_path / "session_schedule.csv"
    pd.DataFrame({"session_date": ["2025-07-03"]}).to_csv(schedule_path, index=False)
    cfg = OmegaConf.create({"data": {"session_schedule_file": str(schedule_path)}})

    with pytest.raises(ValueError, match="scheduled_ny_close_broker_time"):
        scheduled_session_close_map(cfg)
