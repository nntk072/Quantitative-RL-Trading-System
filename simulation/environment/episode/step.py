"""Composition root for the environment step transition services."""

from __future__ import annotations

from ..accounting.step import StepAccountingRuntimeMixin
from ..entries.action_intent import ActionIntentRuntimeMixin
from ..entries.funnel import EntryFunnelRuntimeMixin
from ..step_action_execution import StepActionExecutionMixin
from .constraints import StepConstraintsRuntimeMixin
from .end import StepEndRuntimeMixin
from .info import StepInfoRuntimeMixin


class StepRuntimeMixin(
    ActionIntentRuntimeMixin,
    StepConstraintsRuntimeMixin,
    StepActionExecutionMixin,
    StepAccountingRuntimeMixin,
    EntryFunnelRuntimeMixin,
    StepInfoRuntimeMixin,
    StepEndRuntimeMixin,
):
    """Compose action, constraint, execution, accounting and episode stages."""

    pass


__all__ = ["StepRuntimeMixin"]
