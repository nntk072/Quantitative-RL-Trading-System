from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CURRENT_CONFIG_SCHEMA_VERSION = 1


class ConfigSchemaError(ValueError):
    pass


def reject_unknown_keys(
    values: Mapping[str, Any], schema: Mapping[str, Any], *, path: str = "config"
) -> None:
    """Reject unknown keys and incompatible nested value shapes."""
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise ConfigSchemaError(f"unknown keys at {path}: {unknown}")
    for key, value in values.items():
        schema_value = schema[key]
        value_is_mapping = isinstance(value, Mapping)
        schema_is_mapping = isinstance(schema_value, Mapping)
        if value_is_mapping and not schema_is_mapping:
            raise ConfigSchemaError(f"expected a scalar at {path}.{key}, received a nested mapping")
        if schema_is_mapping and not value_is_mapping:
            raise ConfigSchemaError(f"expected a mapping at {path}.{key}, received a scalar")
        if value_is_mapping and schema_is_mapping:
            reject_unknown_keys(value, schema_value, path=f"{path}.{key}")
            continue
        if schema_value is None or value is None:
            continue
        if isinstance(schema_value, bool):
            matches = isinstance(value, bool)
        elif isinstance(schema_value, int):
            matches = isinstance(value, int) and not isinstance(value, bool)
        elif isinstance(schema_value, float):
            matches = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            matches = type(value) is type(schema_value)
        if not matches:
            raise ConfigSchemaError(
                f"expected {type(schema_value).__name__} at {path}.{key}, "
                f"received {type(value).__name__}"
            )
