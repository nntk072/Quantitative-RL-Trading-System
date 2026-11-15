# Action schema and parameterization contract

This page summarizes the subject contract. See the canonical [action schemas
reference](../action_schemas.md) for complete coordinate tables and
configuration details.

## Schema identity

`decisioning.actions.build_action_schema` constructs the `overlay-action-v2`
layout. Its base coordinates are `intensity`, `stop`, `risk`, `target`, and
`exit`; flags add or replace named coordinates. Direction is prepended,
management modes precede exit, multi-target mode replaces `target` with three
target selections, and simplex mode adds `z1` and `z2` while requiring
multi-target mode.

The setup-conditioned builder delegates to
`decisioning.trade_setup.build_trade_setup_action_schema`. It uses
`trade-setup-overlay-action-v1`, or
`trade-setup-entry-execution-action-v2` when entry execution is enabled. The
separate `discrete-trading-v1` schema contains 20 named choices.

Schema version, key, flags, and ordered coordinate names jointly define
meaning. Layouts with equal width may have different meanings. Checkpoints and
consumers must validate serialized metadata rather than infer a schema from
array length.

## Entry parameterization

With entry execution enabled, raw `entry_execution < 0` selects market entry;
zero or greater selects limit entry. The normalized limit-offset coordinate
maps to the configured ATR range. The TTL coordinate maps to an integer bar
count in its configured range. These are policy controls, not accepted orders
or fills; execution and risk approval happen downstream.

## Configuration and verification

`build_action_schema_from_config` resolves setup actions, optional controls,
multi-target mode, simplex sizing, and entry execution. Agent entry execution
requires setup-conditioned actions. Relevant tests are
`tests/unit/decisioning/test_action_schema_config.py`,
`tests/unit/decisioning/test_trade_setup_contract.py`,
`tests/integration/test_action_schema_contract.py`, and
`tests/unit/models/test_action_schema_checkpoint.py`.

The subject example is deterministic and schema-only. Learned policy quality,
fill quality, and trading performance have not been measured by this
reference.
