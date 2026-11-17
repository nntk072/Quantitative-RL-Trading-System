from __future__ import annotations

from pathlib import Path
from typing import Any

from research_tools.studies.handlers.market_data import _tick_coverage_and_quote_age


def test_tick_coverage_audit_blocks_fill_claims_when_quote_age_is_unmeasured(
    tmp_path: Path, monkeypatch: Any
) -> None:
    def fake_coverage_audit(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "source_count_reconciled",
            "symbol": "US100.cash",
            "m1_rows": 100,
            "minutes_quote_complete": 97,
            "minutes_quote_incomplete": 3,
            "minutes_with_tick_count_mismatch": 2,
            "raw_tick_rows_without_valid_quote": 1,
        }

    monkeypatch.setattr(
        "research_tools.market_data.market_data.audit_tick_quote_coverage.build_coverage_audit",
        fake_coverage_audit,
    )

    report = _tick_coverage_and_quote_age(tmp_path, tmp_path / "audit-output")

    assert report["diagnostic_status"] == "incomplete_quote_age_not_measured"
    assert report["quote_age_distribution"] == "not measured by the registered source audit"
    assert report["dependent_fill_claims"] == "blocked_until_carried_side_age_is_measured"
