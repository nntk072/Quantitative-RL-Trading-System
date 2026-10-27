from __future__ import annotations

from types import SimpleNamespace

import pytest

from decisioning.thesis import thesis_observation_schema, validate_thesis_observation_schema
from training.artifacts.manifests import _observation_schema_manifest


def test_thesis_observation_schema_is_checkpoint_checked() -> None:
    expected = thesis_observation_schema()
    model = SimpleNamespace(_thesis_observation_schema=expected)
    validate_thesis_observation_schema(model._thesis_observation_schema, expected)
    validate_thesis_observation_schema(None, None)

    with pytest.raises(ValueError, match="thesis observation schema"):
        validate_thesis_observation_schema(None, expected)
    with pytest.raises(ValueError, match="thesis observation schema"):
        validate_thesis_observation_schema(model._thesis_observation_schema, None)


def test_training_observation_manifest_records_thesis_mask_schema() -> None:
    account_schema = SimpleNamespace(to_dict=lambda: {"version": "account-state-v1"})
    env = SimpleNamespace(
        observation_schema=account_schema,
        regime_observation_schema=None,
        thesis_observation_schema=thesis_observation_schema(),
    )

    manifest = _observation_schema_manifest(env)

    assert manifest is not None
    assert manifest["version"] == "account-state-v1"
    assert manifest["thesis_observation"] == thesis_observation_schema()
