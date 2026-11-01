"""Checks for the generated canonical-configuration reference."""

from __future__ import annotations

from tools.documentation.configuration_reference import (
    _inferred_type,
    render_configuration_reference,
)


def test_configuration_reference_renders_leaf_defaults_and_section_owners() -> None:
    rendered = render_configuration_reference(
        {
            "env": {"observation_schema_version": "account-state-v1", "max_steps": None},
            "risk": {"enabled": True, "limit": 1000.0},
        }
    )

    assert '`env.observation_schema_version` | `string` | `"account-state-v1"`' in rendered
    assert "`env.observation_schema_version`" in rendered
    assert "simulation/environment and decisioning" in rendered
    assert "`risk.enabled` | `boolean` | `true` | `trading/risk`" in rendered
    assert "`risk.limit` | `number` | `1000.0` | `trading/risk`" in rendered
    assert "`env` |" not in rendered


def test_yaml_value_type_inference_checks_boolean_before_integer() -> None:
    assert _inferred_type(False) == "boolean"
    assert _inferred_type(None) == "null"
