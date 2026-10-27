from __future__ import annotations

from types import SimpleNamespace

import pytest

from decisioning.thesis import thesis_observation_schema
from learning.rl.agent import validate_model_thesis_observation_schema
from training.artifacts.manifests import _observation_schema_manifest


def test_thesis_observation_schema_is_checkpoint_checked() -> None:
    expected = thesis_observation_schema()
    model = SimpleNamespace(_thesis_observation_schema=expected)
    validate_model_thesis_observation_schema(model, expected)
    validate_model_thesis_observation_schema(SimpleNamespace(), None)

    with pytest.raises(ValueError, match="thesis observation schema"):
        validate_model_thesis_observation_schema(SimpleNamespace(), expected)
    with pytest.raises(ValueError, match="thesis observation schema"):
        validate_model_thesis_observation_schema(model, None)


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
