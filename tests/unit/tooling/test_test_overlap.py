from tools.quality.test_overlap import _test_module, rank_overlaps


def test_test_module_extracts_context_owner() -> None:
    assert _test_module("tests/unit/test_risk.py::test_cap|run") == "tests/unit/test_risk.py"
    assert _test_module("") is None


def test_overlap_ranking_uses_shared_production_lines() -> None:
    common = {("trading/risk.py", line) for line in range(20)}
    coverage = {
        "tests/unit/test_risk.py": common | {("trading/risk.py", 21)},
        "tests/integration/test_risk_flow.py": common | {("simulation/env.py", 1)},
        "tests/unit/test_data.py": {("market_data/load.py", line) for line in range(30)},
    }

    ranked = rank_overlaps(coverage, minimum_shared_lines=12)

    assert len(ranked) == 1
    assert ranked[0]["shared_lines"] == 20
    assert ranked[0]["shared_files"] == 1
    assert ranked[0]["jaccard"] == 20 / 22
