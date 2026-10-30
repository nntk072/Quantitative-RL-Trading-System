from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_LAYOUT_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")


def _validate_layout_component(value: str, label: str) -> str:
    if not isinstance(value, str) or not _LAYOUT_COMPONENT.fullmatch(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactLayout:
    root: Path

    def runs(self) -> Path:
        return self.root / "runs"

    def run(self, run_id: str) -> Path:
        return self.runs() / _validate_layout_component(run_id, "run id")

    def timestamped_run(self, name: str, *, timestamp: datetime | None = None) -> Path:
        """Build the established timestamped run path without creating it."""
        _validate_layout_component(name, "run name")
        created_at = timestamp or datetime.now()
        timestamp_text = created_at.strftime("%Y%m%d_%H%M%S_%f")
        return self.root / f"{timestamp_text}_{name}"

    def campaigns(self) -> Path:
        return self.root / "campaigns"

    def campaign(self, campaign_id: str) -> Path:
        return self.campaigns() / _validate_layout_component(campaign_id, "campaign id")

    def gpu_campaign(self, campaign_id: str) -> CampaignArtifactLayout:
        """Resolve the established GPU campaign path through the artifact layout."""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", campaign_id):
            raise ValueError(f"unsafe campaign id: {campaign_id!r}")
        return CampaignArtifactLayout(self.root / "gpu_campaigns" / campaign_id)

    def evaluation(self, evaluation_id: str) -> Path:
        return self.root / "evaluation" / _validate_layout_component(evaluation_id, "evaluation id")

    def research(self) -> Path:
        return self.root / "research"

    def reports(self) -> Path:
        return self.root / "reports"


@dataclass(frozen=True, slots=True)
class CampaignArtifactLayout:
    """Named artifact paths for a campaign, preserving its established on-disk layout."""

    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "campaign.json"

    @property
    def controller_lock(self) -> Path:
        return self.root / "controller.lock"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def worker_logs(self) -> Path:
        return self.logs / "workers"

    @property
    def failure_logs(self) -> Path:
        return self.logs / "failures"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def markers(self) -> Path:
        return self.root / "markers"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def source_snapshot(self) -> Path:
        return self.root / "source_snapshot.zip"

    @property
    def queue(self) -> Path:
        return self.root / "queue.jsonl"

    def report(self, name: str) -> Path:
        return self._named_file(self.reports, name, "report")

    def root_file(self, name: str) -> Path:
        return self._named_file(self.root, name, "artifact")

    def log(self, name: str) -> Path:
        return self._named_file(self.logs, name, "log")

    def worker_log(self, run_key: str, attempt: int) -> Path:
        self._validate_run_key(run_key)
        self._validate_attempt(attempt)
        return self.worker_logs / f"{run_key}__attempt{attempt}.log"

    def attempt(self, run_key: str, attempt: int) -> Path:
        self._validate_run_key(run_key)
        self._validate_attempt(attempt)
        return self.runs / "attempts" / run_key / f"attempt{attempt}"

    def run_attempts(self, run_key: str) -> Path:
        self._validate_run_key(run_key)
        return self.runs / "attempts" / run_key

    def completion_marker(self, run_key: str) -> Path:
        self._validate_run_key(run_key)
        return self.markers / f"{run_key}.done"

    def bootstrap_checkpoint(self, run_key: str) -> Path:
        self._validate_run_key(run_key)
        return self.root / "bootstrap_checkpoints" / f"{run_key}.zip"

    def resolve_recorded_path(self, value: str | Path) -> Path:
        """Resolve a manifest path without allowing it to escape the campaign root."""
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved_root = self.root.resolve()
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_root):
            raise ValueError("recorded campaign path escapes its campaign directory")
        return resolved_candidate

    def recovery_checkpoint(self, value: str | Path) -> Path:
        """Resolve a recorded checkpoint only when it remains inside this campaign."""
        try:
            return self.resolve_recorded_path(value)
        except ValueError:
            raise ValueError("campaign checkpoint path escapes its campaign directory") from None

    def ensure_controller_directories(self) -> None:
        for directory in (
            self.worker_logs,
            self.failure_logs,
            self.runs,
            self.markers,
            self.reports,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_run_key(run_key: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,150}", run_key):
            raise ValueError(f"unsafe campaign run key: {run_key!r}")

    @staticmethod
    def _validate_attempt(attempt: int) -> None:
        if type(attempt) is not int or attempt < 1:
            raise ValueError("campaign attempt must be a positive integer")

    @staticmethod
    def _named_file(directory: Path, name: str, kind: str) -> Path:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError(f"campaign {kind} name must be a file name")
        return directory / name
