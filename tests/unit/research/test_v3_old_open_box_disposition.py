from pathlib import Path
from typing import Any, cast

import pytest
from omegaconf import OmegaConf
from scripts.research.audits.build_v3_old_open_box_disposition import build_dispositions
from scripts.research.audits.v3_full_plan_registry import load_catalog
from scripts.research.audits.v3_full_plan_runner import initialize_progress


def test_old_box_map_contains_exactly_70_items_and_can_resolve(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    mapping_value = OmegaConf.to_container(
        OmegaConf.load(root / "config/research/v3_old_open_box_map.yaml"), resolve=True
    )
    assert isinstance(mapping_value, dict)
    mapping = cast(dict[str, Any], mapping_value)
    assert mapping["item_count"] == 70
    catalog = load_catalog(root / "config/research/v3_full_todo_catalog.yaml")
    progress = initialize_progress(catalog, source_sha="a" * 40)
    for row in progress["tasks"].values():
        row["status"] = "PASS"
    result = build_dispositions(mapping, progress)
    assert result["item_count"] == 70
    assert result["all_terminal"] is True


def test_duplicate_historical_open_box_ids_are_rejected() -> None:
    items: list[dict[str, Any]] = [
        {"old_open_id": old_id, "todo_refs": [1], "disposition_path": "TODO 1"}
        for old_id in range(1, 71)
    ]
    mapping = {
        "item_count": 70,
        "items": items,
    }
    items[1]["old_open_id"] = 1
    with pytest.raises(ValueError, match="exactly 1..70"):
        build_dispositions(mapping, {"tasks": {"1": {"status": "PASS"}}})
