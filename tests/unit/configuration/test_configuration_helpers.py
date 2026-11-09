from __future__ import annotations

import pytest
from omegaconf import OmegaConf

from configuration.configuration_loader import load_config_overlay, merge_config_overlay
from configuration.hashing import canonical_config_bytes, config_sha256
from configuration.paths import RepositoryPaths, repository_root
from configuration.schema import ConfigSchemaError, _resolve_schema_reference, reject_unknown_keys


def test_configuration_serialization_and_repository_path_helpers(tmp_path) -> None:
    config = {"b": 2, "a": 1}
    assert canonical_config_bytes(config) == b'{"a":1,"b":2}'
    assert len(config_sha256(config)) == 64

    paths = RepositoryPaths.from_root(tmp_path)
    assert paths.root == tmp_path.resolve()
    assert paths.outputs == tmp_path.resolve() / "outputs"
    with pytest.raises(FileNotFoundError, match="could not locate repository root"):
        repository_root(tmp_path)


def test_repository_root_accepts_file_anchor() -> None:
    root = repository_root(__file__)
    assert (root / "pyproject.toml").is_file()
    assert repository_root(root) == root


def test_configuration_overlay_and_override_reject_invalid_roots(tmp_path) -> None:
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("- one\n", encoding="utf-8")
    with pytest.raises(ValueError, match="overlay root must be a mapping"):
        load_config_overlay(scalar)

    with pytest.raises(ValueError, match="base and overlay roots must be mappings"):
        merge_config_overlay(OmegaConf.create([]), {})  # type: ignore[arg-type]


def test_configuration_override_rejects_malformed_list() -> None:
    from configuration.configuration_loader import load_config

    with pytest.raises(ValueError, match="invalid list override"):
        load_config(["features.ema_periods=[9,"])


def test_schema_reference_resolution_handles_literals_missing_paths_and_cycles() -> None:
    assert _resolve_schema_reference({"a": 1}, "literal") == "literal"
    assert _resolve_schema_reference({}, "${missing.path}") is None
    assert _resolve_schema_reference({"a": "${a}"}, "${a}") is None


def test_schema_validation_rejects_broken_references_and_container_shapes() -> None:
    with pytest.raises(ConfigSchemaError, match="has no declared target"):
        reject_unknown_keys({"value": 2}, {"value": "${missing.target}"})
    with pytest.raises(ConfigSchemaError, match="expected a scalar"):
        reject_unknown_keys({"value": {"nested": 1}}, {"value": 1})
    with pytest.raises(ConfigSchemaError, match="expected a mapping"):
        reject_unknown_keys({"value": 1}, {"value": {"nested": 1}})
