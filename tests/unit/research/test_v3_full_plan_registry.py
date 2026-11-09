from pathlib import Path

from scripts.research.audits.v3_full_plan_registry import load_catalog


def test_full_v3_catalog_is_exact_1_to_162_and_repository_paths_exist() -> None:
    root = Path(__file__).resolve().parents[3]
    catalog = load_catalog(root / "config/research/v3_full_todo_catalog.yaml")
    assert [row["id"] for row in catalog["tasks"]] == list(range(1, 163))
    assert len(catalog["tasks"]) == 162
    assert set(catalog["barriers"]) == {"B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"}
    assert catalog["tasks_by_id"][162]["title"] == "FINISHED condition"
    for todo in (90, 101, 105, 122, 123, 132, 142, 149, 151, 156, 162):
        assert catalog["tasks_by_id"][todo]["canonical_tools"]
