"""Learning paradigms and their backend-specific fitting implementations."""

from learning.contracts import FitRequest, FitResult, Learner
from learning.learner_factory import build_learner

__all__ = ["FitRequest", "FitResult", "Learner", "build_learner"]
