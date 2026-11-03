from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from omegaconf import OmegaConf

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts/research/analysis/features/verify_real_market_feature_prefix_invariance.py"
)
SPEC = importlib.util.spec_from_file_location("feature_prefix_invariance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_feature_group_key_tracks_source_clock_model() -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {"tz": "Etc/GMT-3", "timestamp_clock": "native"},
            "session": {"tz": "Etc/GMT-3"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}},
        }
    )

    native_key = AUDIT.feature_config_key(cfg)
    cfg.data.timestamp_clock = "ftmo_mt5_us_dst"

    assert AUDIT.feature_config_key(cfg) != native_key


def test_feature_group_key_tracks_training_fit_interval() -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {
                "tz": "Etc/GMT-3",
                "timestamp_clock": "native",
                "split": {
                    "train_start": "2024-12-30",
                    "train_end": "2025-12-31",
                    "test_start": "2026-01-01",
                },
            },
            "session": {"tz": "Etc/GMT-3"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}},
        }
    )

    original_key = AUDIT.feature_config_key(cfg)
    cfg.data.split.train_end = "2025-11-30"

    assert AUDIT.feature_config_key(cfg) != original_key


def test_configured_training_mask_honors_train_start_and_end() -> None:
    index = pd.date_range("2024-12-29", periods=4, freq="D", tz="Etc/GMT-3")
    cfg = OmegaConf.create(
        {
            "data": {
                "split": {
                    "train_start": "2024-12-30",
                    "train_end": "2024-12-31",
                    "test_start": "2025-01-01",
                }
            }
        }
    )

    mask = AUDIT.configured_training_mask(index, cfg)

    assert mask.tolist() == [False, True, True, False]


def test_feature_group_key_tracks_configured_m1_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {
                "tz": "Etc/GMT-3",
                "timestamp_clock": "native",
                "primary": "US100.cash",
                "secondary": "US500.cash",
                "split": {"train_start": "2024-12-30", "train_end": "2025-12-31"},
            },
            "session": {"tz": "Etc/GMT-3"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}},
        }
    )
    inputs = {
        (dataset, symbol): tmp_path / f"{dataset}-{symbol}.csv"
        for dataset in ("training", "testing")
        for symbol in ("US100.cash", "US500.cash")
    }
    for path in inputs.values():
        path.write_text("same input", encoding="utf-8")

    def resolve_input(_cfg: Any, symbol: str, dataset_name: str = "training") -> Path:
        return inputs[(dataset_name, symbol)]

    monkeypatch.setattr(AUDIT, "configured_m1_path", resolve_input)
    original_key = AUDIT.feature_config_key(cfg)
    inputs[("training", "US100.cash")].write_text("different input", encoding="utf-8")

    assert AUDIT.feature_config_key(cfg) != original_key


def test_feature_group_key_tracks_risk_point_size_and_price_grid() -> None:
    cfg = OmegaConf.create(
        {
            "features": {},
            "data": {
                "tz": "Etc/GMT-3",
                "timestamp_clock": "native",
                "price_discretization": {"enabled": False, "increment": 0.25},
            },
            "costs": {"point_size": 0.25},
            "session": {"tz": "Etc/GMT-3", "start": "16:30", "end": "23:00"},
            "strategy": {"session": {"timezone": "Etc/GMT-3"}, "ifvg": {}},
        }
    )
    raw_key = AUDIT.feature_config_key(cfg)
    cfg.data.price_discretization.enabled = True

    assert AUDIT.feature_config_key(cfg) != raw_key
    grid_key = AUDIT.feature_config_key(cfg)
    cfg.costs.point_size = 0.5

    assert AUDIT.feature_config_key(cfg) != grid_key


def test_feature_groups_have_one_effective_builder_configuration() -> None:
    variant_names = [
        line.strip()
        for line in AUDIT.DEFAULT_VARIANT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    groups: dict[str, set[str]] = {}
    for name in variant_names:
        cfg, _resolved = AUDIT.config_for_variant(name)
        builder_inputs = {
            "features": OmegaConf.to_container(cfg.features, resolve=True),
            "strategy.ifvg": OmegaConf.to_container(
                OmegaConf.select(cfg, "strategy.ifvg"), resolve=True
            ),
            "data.tz": str(OmegaConf.select(cfg, "data.tz")),
            "data.timestamp_clock": str(OmegaConf.select(cfg, "data.timestamp_clock")),
            "data.session_schedule_file": str(OmegaConf.select(cfg, "data.session_schedule_file")),
            "costs.point_size": str(OmegaConf.select(cfg, "costs.point_size")),
            "session.tz": str(OmegaConf.select(cfg, "session.tz")),
            "session.start": str(OmegaConf.select(cfg, "session.start")),
            "session.end": str(OmegaConf.select(cfg, "session.end")),
            "strategy.session.timezone": str(OmegaConf.select(cfg, "strategy.session.timezone")),
        }
        encoded = json.dumps(builder_inputs, sort_keys=True, default=str)
        groups.setdefault(AUDIT.feature_config_key(cfg), set()).add(encoded)

    assert groups
    assert all(len(configurations) == 1 for configurations in groups.values())


def test_inventory_profiles_resolve_to_effective_feature_builder_groups() -> None:
    inventory_path = (
        AUDIT.ROOT / "evidence/research/feature_causality/feature_configuration_inventory.json"
    )
    profiles, inventory_hash = AUDIT.load_inventory_profiles(inventory_path)
    groups = {AUDIT.feature_config_key(cfg) for _, cfg, _ in profiles}

    assert inventory_hash
    assert len(profiles) == 130
    assert len({meta["feature_config_sha256"] for _, _, meta in profiles}) == 18
    # The same feature tree can still require separate builds when the
    # effective price-grid configuration differs.
    assert len(groups) == 19


def test_inventory_rejects_a_profile_feature_hash_mismatch(tmp_path: Path) -> None:
    inventory_path = (
        AUDIT.ROOT / "evidence/research/feature_causality/feature_configuration_inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["profiles"][0]["feature_config_sha256"] = "0" * 64
    altered_inventory_path = tmp_path / "feature_inventory.json"
    altered_inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

    with pytest.raises(ValueError, match="resolved feature tree differs from inventory"):
        AUDIT.load_inventory_profiles(altered_inventory_path)


def test_default_variant_file_is_the_registered_experiment_run_list() -> None:
    expected = AUDIT.ROOT / "config" / "experiment_runs" / "variant_list.txt"

    assert AUDIT.DEFAULT_VARIANT_FILE == expected
    assert AUDIT.DEFAULT_VARIANT_FILE.is_file()


def test_training_dataset_resolves_the_configured_local_m1_export() -> None:
    cfg, _resolved = AUDIT.config_for_variant("ladder_a0_flat")

    source = AUDIT.configured_m1_path(cfg, str(cfg.data.primary))

    assert source == AUDIT.ROOT / "data/training/US100.cash_M1_202412300105_202610162349.csv"
    assert source.is_file()


def test_testing_dataset_resolves_its_separate_local_m1_export() -> None:
    cfg, _resolved = AUDIT.config_for_variant("ladder_a0_flat")

    source = AUDIT.configured_m1_path(cfg, str(cfg.data.primary), "testing")

    assert source == AUDIT.ROOT / "data/testing/US100.cash_M1_202412300105_202610162349.csv"
    assert source.is_file()


def test_cutoffs_must_leave_later_rows_for_comparison() -> None:
    index = pd.date_range("2025-12-30", periods=3, freq="D", tz="Etc/GMT-3")

    assert AUDIT.resolve_cutoffs(["2025-12-31"], index) == [index[1]]
    with pytest.raises(ValueError, match="later rows available"):
        AUDIT.resolve_cutoffs(["2026-03-09"], index)


def test_compare_prefix_accepts_equal_values_and_nan_masks() -> None:
    index = pd.date_range("2025-12-30", periods=3, freq="D", tz="Etc/GMT-3")
    reference = pd.DataFrame({"signal": [1.0, float("nan"), float("inf")]}, index=index)

    result = AUDIT.compare_prefix(reference, reference.copy(), index[-1])

    assert result["passed"] is True
    assert result["compared_values"] == 3
    assert result["max_abs_delta"] == 0.0


def test_compare_prefix_reports_numeric_and_nan_mask_changes() -> None:
    index = pd.date_range("2025-12-30", periods=3, freq="D", tz="Etc/GMT-3")
    reference = pd.DataFrame({"signal": [1.0, float("nan"), 3.0]}, index=index)
    candidate = pd.DataFrame({"signal": [1.01, 2.0, 3.0]}, index=index)

    result = AUDIT.compare_prefix(reference, candidate, index[-1])

    assert result["passed"] is False
    assert result["changed_feature_count"] == 1
    assert result["changed_features"][0]["mismatch_rows"] == 2
    assert result["changed_features"][0]["nan_mask_mismatches"] == 1
    assert result["changed_features"][0]["max_abs_delta"] == pytest.approx(0.01)


@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (
            pd.DataFrame(
                {"signal": [1.0]}, index=pd.date_range("2025-12-30", periods=1, tz="Etc/GMT-3")
            ),
            "prefix indexes differ",
        ),
        (
            pd.DataFrame(
                {"other": [1.0]}, index=pd.date_range("2025-12-30", periods=2, tz="Etc/GMT-3")
            ),
            "feature columns differ",
        ),
    ],
)
def test_compare_prefix_rejects_index_or_column_mismatch(
    candidate: pd.DataFrame, reason: str
) -> None:
    index = pd.date_range("2025-12-30", periods=2, freq="D", tz="Etc/GMT-3")
    reference = pd.DataFrame({"signal": [1.0, 2.0]}, index=index)

    result = AUDIT.compare_prefix(reference, candidate, index[-1])

    assert result["passed"] is False
    assert result["reason"] == reason
