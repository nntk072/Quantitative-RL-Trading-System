from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from market_data.news.fred import events_from_fred_json, fetch_release_dates


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any], timeout: int) -> SimpleNamespace:
        self.calls.append(params)
        release_id = params["release_id"]
        dates = {
            10: "2025-01-15",
            46: "2025-01-14",
            50: "2025-01-10",
            53: "2025-01-30",
            192: "2025-01-07",
        }
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "release_dates": [
                    {
                        "release_id": release_id,
                        "release_name": f"release {release_id}",
                        "date": dates[release_id],
                    }
                ]
            },
        )


def test_fetch_requests_each_configured_release_with_the_key() -> None:
    session = _FakeSession()

    payload = fetch_release_dates("KEY", "2025-01-01", "2025-12-31", session=session)

    assert sorted(call["release_id"] for call in session.calls) == [10, 46, 50, 53, 192]
    assert all(call["api_key"] == "KEY" for call in session.calls)  # pragma: allowlist secret
    assert len(payload["release_dates"]) == 5


def test_events_use_standard_et_times_and_skip_unconfigured_ids(tmp_path: Path) -> None:
    path = tmp_path / "fred.json"
    path.write_text(
        json.dumps(
            {
                "release_dates": [
                    {
                        "release_id": 50,
                        "release_name": "Employment Situation",
                        "date": "2025-02-07",
                    },
                    {"release_id": 10, "release_name": "CPI", "date": "2025-07-15"},
                    {"release_id": 999, "release_name": "Other", "date": "2025-07-15"},
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = events_from_fred_json(path)

    assert [row.category for row in rows] == ["NFP", "CPI"]
    # 08:30 New York is 13:30 UTC in winter and 12:30 UTC in summer.
    assert rows[0].utc_time == datetime(2025, 2, 7, 13, 30, tzinfo=UTC)
    assert rows[1].utc_time == datetime(2025, 7, 15, 12, 30, tzinfo=UTC)
    assert all(len(row.source_sha256) == 64 for row in rows)


@pytest.mark.parametrize("missing", [True])
def test_main_refuses_to_run_without_api_key(
    monkeypatch: pytest.MonkeyPatch, missing: bool
) -> None:
    from market_data.news import fred

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        fred.main(["--out", "unused.json"])
