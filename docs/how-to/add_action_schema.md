# Add an action schema

An action schema defines how policy outputs represent a decision. It is a
versioned interface between learning, the environment, evaluation, and stored
checkpoints.

1. Write the decision semantics and coordinate/category mapping before
   implementation. Define bounds, masks, no-trade behavior, and invalid-input
   handling.
2. Add a distinct schema version when serialized meaning changes; do not reuse
   a version string for different semantics.
3. Integrate decoding through the existing decisioning contract. Keep policy
   outputs separate from trading intents, accepted orders, and fills.
4. Test encode/decode round trips, category masks, invalid actions, all optional
   layouts, and deterministic action meaning.
5. Add explicit compatibility translation for old observations/actions and
   checkpoints. Verify inference parity against a preserved fixture.
6. Document fields in the [action reference](../reference/action_schemas.md)
   and any model-specific policy composition.

Do not change execution behavior as an incidental consequence of renaming an
action coordinate.
