from __future__ import annotations

from enum import StrEnum


class RetentionClass(StrEnum):
    """Retention policies for generated artifacts."""

    DISPOSABLE = "disposable"
    RUN_RETAINED = "run-retained"
    EVIDENCE_RETAINED = "evidence-retained"
    BASELINE_PROMOTABLE = "baseline-promotable"
