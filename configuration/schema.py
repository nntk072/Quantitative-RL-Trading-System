from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CURRENT_CONFIG_SCHEMA_VERSION = 1


class ConfigSchemaError(ValueError):
    """Raised when configuration data violates the repository schema."""

    pass


def _resolve_schema_reference(
    schema: Mapping[str, Any], value: str, *, _seen: frozenset[str] = frozenset()
) -> Any:
    """Resolve a full OmegaConf path reference to its declared schema leaf.

    Args:
        schema: Schema tree containing the referenced configuration path.
        value: Value that may contain an OmegaConf interpolation.
        _seen: References already followed, used to stop interpolation cycles.

    Returns:
        Referenced schema leaf, original literal, or ``None`` for invalid/cyclic references.
    """
    if not (value.startswith("${") and value.endswith("}")):
        return value
    if value in _seen:
        return None
    target: Any = schema
    for component in value[2:-1].split("."):
        if not isinstance(target, Mapping) or component not in target:
            return None
        target = target[component]
    if isinstance(target, str) and target.startswith("${") and target.endswith("}"):
        return _resolve_schema_reference(schema, target, _seen=_seen | {value})
    return target


def reject_unknown_keys(
    values: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    path: str = "config",
    _schema_root: Mapping[str, Any] | None = None,
) -> None:
    """Reject unknown keys and incompatible nested value shapes.

    Args:
        values: Values to process, in input order.
        schema: Key-value data used for the schema.
        path: Path to the input file or directory.
        _schema_root: Root schema used to resolve references in nested fields.
    """
    schema_root = schema if _schema_root is None else _schema_root
    unknown = sorted(set(values) - set(schema))
    if unknown:
        raise ConfigSchemaError(f"unknown keys at {path}: {unknown}")
    for key, value in values.items():
        schema_value = schema[key]
        if (
            isinstance(schema_value, str)
            and schema_value.startswith("${")
            and schema_value.endswith("}")
        ):
            # A default value may intentionally remain an OmegaConf reference
            # (for example, a plotting level list linked to the feature list).
            # Its target is validated at the referenced config path below.
            if value == schema_value:
                continue
            referenced_schema = _resolve_schema_reference(schema_root, schema_value)
            if referenced_schema is None:
                raise ConfigSchemaError(
                    f"schema reference at {path}.{key} has no declared target: {schema_value}"
                )
            schema_value = referenced_schema
        value_is_mapping = isinstance(value, Mapping)
        schema_is_mapping = isinstance(schema_value, Mapping)
        if value_is_mapping and not schema_is_mapping:
            raise ConfigSchemaError(f"expected a scalar at {path}.{key}, received a nested mapping")
        if schema_is_mapping and not value_is_mapping:
            raise ConfigSchemaError(f"expected a mapping at {path}.{key}, received a scalar")
        if value_is_mapping and schema_is_mapping:
            reject_unknown_keys(
                value,
                schema_value,
                path=f"{path}.{key}",
                _schema_root=schema_root,
            )
            continue
        if schema_value is None or value is None:
            continue
        if isinstance(schema_value, list):
            matches = isinstance(value, list)
            if matches and schema_value:
                expected_types = {type(item) for item in schema_value}
                for item in value:
                    if expected_types == {float}:
                        item_matches = isinstance(item, (int, float)) and not isinstance(item, bool)
                    else:
                        item_matches = type(item) in expected_types
                    if not item_matches:
                        matches = False
                        break
        elif isinstance(schema_value, bool):
            matches = isinstance(value, bool)
        elif isinstance(schema_value, int):
            matches = isinstance(value, int) and not isinstance(value, bool)
        elif isinstance(schema_value, float):
            matches = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            matches = type(value) is type(schema_value)
        if not matches:
            expected_type = (
                f"list[{','.join(sorted(item.__name__ for item in {type(x) for x in schema_value}))}]"
                if isinstance(schema_value, list) and schema_value
                else type(schema_value).__name__
            )
            raise ConfigSchemaError(
                f"expected {expected_type} at {path}.{key}, received {type(value).__name__}"
            )
