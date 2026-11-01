"""Adapter for deterministic rule functions at the decision boundary."""

from __future__ import annotations

from collections.abc import Callable

from decisioning.contracts import Decision, DecisionInput, PredictorMetadata


class RuleBasedDecisionProvider:
    """Wrap a pure decision rule in the same protocol used by learned providers."""

    def __init__(
        self,
        rule: Callable[[DecisionInput], Decision],
        metadata: PredictorMetadata,
    ) -> None:
        """Initialize RuleBasedDecisionProvider and its owned state.

        Args:
            rule: Rule used by the operation described above.
            metadata: Metadata used by the operation described above.
        """
        self._rule = rule
        self._metadata = metadata

    @property
    def metadata(self) -> PredictorMetadata:
        """Return the schema and identity advertised by the wrapped rule.

        Returns:
            Result of return the schema and identity advertised by the wrapped rule.
        """
        return self._metadata

    def predict(self, input: DecisionInput, *, deterministic: bool = True) -> Decision:
        """Apply the rule after checking its input and output schema contracts.

        Args:
            input: Versioned observation and action-schema context.
            deterministic: Accepted for provider parity; pure rules are deterministic.

        Returns:
            The rule's decision after its action schema is validated.

        Raises:
            ValueError: If the input or produced action schema differs from metadata.
        """
        del deterministic
        if input.schema_version != self._metadata.input_schema_version:
            raise ValueError(
                f"observation schema {input.schema_version!r} differs from provider schema "
                f"{self._metadata.input_schema_version!r}"
            )
        decision = self._rule(input)
        if decision.action_schema != self._metadata.action_schema:
            raise ValueError("rule decision action schema differs from provider metadata")
        return decision


__all__ = ["RuleBasedDecisionProvider"]
