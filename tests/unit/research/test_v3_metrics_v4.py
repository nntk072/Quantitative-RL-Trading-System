import json
from pathlib import Path

from scripts.research.audits.verify_v3_metrics_v4 import verify_file


def _payload() -> dict[str, object]:
    return {
        "metric_definition_version": "qrl.performance_metrics.v4",
        "n_trades": 0,
        "total_pnl": 0.0,
        "breach_count": 0,
        "breach_event_count": 0,
        "breach_session_count": 0,
        "breach_rate": 0.0,
        "daily_return_count": 1,
        "daily_return_mean_pct": 0.0,
        "daily_return_std_pct": None,
        "time_to_ruin_sessions": 1,
        "ruin_event_observed": False,
        "ruin_time_censored": True,
        "metric_availability": {"daily_return_std_pct": "fewer_than_two_complete_sessions"},
    }


def test_metrics_v4_verifier_accepts_typed_current_payload(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(
        json.dumps({"metrics": _payload()}),
        encoding="utf-8",
    )
    assert verify_file(path)["status"] == "pass"


def test_metrics_v4_verifier_rejects_untyped_ruin_flags(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    payload = _payload()
    payload["ruin_event_observed"] = 0
    path.write_text(json.dumps({"metrics": payload}), encoding="utf-8")
    report = verify_file(path)
    assert report["status"] == "fail"
    assert any("not a typed boolean" in failure for failure in report["failures"])
