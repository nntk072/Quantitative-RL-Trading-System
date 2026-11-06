"""Compatibility exports for the shared simulation entry-state contract."""

from simulation.entry_state import (
    EntryCandidate,
    EntryEvidence,
    EntryStateMachine,
    immutable_setup_levels,
)

__all__ = [
    "EntryCandidate",
    "EntryEvidence",
    "EntryStateMachine",
    "immutable_setup_levels",
]
