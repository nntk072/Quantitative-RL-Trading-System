# Trade-setup candidate catalog

This page defines the ordered categorical candidates used by the
setup-conditioned policy. “Trade setup” is the reader-facing concept; the
serialized implementation currently retains `thesis*` names for checkpoint
compatibility.

## Candidate dimensions

The selectable tuple is:

```text
(entry idea, setup timeframe, direction)
```

| Index order | Values |
|---|---|
| Entry idea | `po3`, `order_block`, `standard_deviation`, `fvg_retest`, `ifvg_retest`, `ifvg_unretested` |
| Setup timeframe | `M1`, `M3`, `M5`, `M10`, `M15`, `M30`, `H1`, `H4`, `D1` |
| Direction | Long, then short |

There are 6 × 9 × 2 = 108 setup tuples plus one explicit no-trade category,
for 109 total categories. ID `0` is always no-trade. IDs `1–54` enumerate
long candidates and `55–108` enumerate short candidates. Within each
direction, ideas are the outer order and timeframes are the inner order.

The stable ID formula is:

```text
candidate_id = 1
             + direction_index * 54
             + idea_index * 9
             + timeframe_index
```

Indices start at zero; long is direction index 0, short is 1. This formula and
ordering are serialized compatibility behavior. Use the catalog resolver
rather than duplicating arithmetic in a policy or report.

## Eligibility columns and mask

For every nonzero candidate, the feature row has an exact column named:

```text
entry_idea_<idea>_<timeframe>_<long|short>
```

Only that exact idea/timeframe/direction column makes that candidate eligible.
Signals from another timeframe or idea are context, not pooled eligibility.
The observation mask uses `1` for eligible and `0` for unavailable; ID `0`
remains eligible. Invalid setup categories must receive zero policy
probability during both action selection and PPO action evaluation.

## Box action encoding

The categorical coordinate is normalized to `[-1, 1]`. Candidate `i` has
center:

```text
center(i) = 2 * (i + 0.5) / 109 - 1
```

Decoding maps the normalized value to the corresponding equal-width category
interval and clamps the upper endpoint to category 108. Keep this encoding,
category ordering, and mask semantics unchanged for the legacy schema.

## Compatibility identifiers

| Domain concept | Current serialized identifier |
|---|---|
| Candidate catalog schema | `thesis-candidate-v1` |
| Observation schema | `thesis-observation-v1` |
| Mask key | `thesis_mask` |
| Action schema | `thesis-overlay-action-v1` |
| Action coordinate | `thesis` |

These names are preserved because checkpoints and historical manifests may
contain them. A canonical wire rename requires a versioned migration and
parity tests over all 109 IDs, masks, Box centers/decoding, no-trade behavior,
optional action layouts, save/load, and deterministic inference. See
[checkpoint compatibility](checkpoint_compatibility.md).

## Ownership

Candidate category meaning belongs to the decision schema; per-timeframe
eligibility comes from feature context; the policy masks the distribution; the
environment still validates execution and account risk. An eligible category
does not guarantee a fill. See [trade setups](../concepts/trade_setups.md) for
the domain explanation and
[`decisioning/README.md`](../../decisioning/README.md) for the local contract
guide.
