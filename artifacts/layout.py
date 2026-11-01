from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_LAYOUT_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")


def _validate_layout_component(value: str, label: str) -> str:
    """Validate layout component.

    Args:
        value: Value to process.
        label: Text or path value identifying the label.

    Returns:
        Text returned by ``_validate_layout_component``.
    """
    if not isinstance(value, str) or not _LAYOUT_COMPONENT.fullmatch(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactLayout:
    """Resolve canonical paths for run, evaluation, research, and report artifacts."""

    root: Path

    def runs(self) -> Path:
        """Return the directory containing ordinary run artifacts.

        Returns:
            Path returned by ``runs``.
        """
        return self.root / "runs"

    def run(self, run_id: str) -> Path:
        """Resolve the directory for one run without creating it.

        Args:
            run_id: Safe path component identifying the run.

        Returns:
            The run artifact directory.
        """
        return self.runs() / _validate_layout_component(run_id, "run id")

    def timestamped_run(self, name: str, *, timestamp: datetime | None = None) -> Path:
        """Build the established timestamped run path without creating it.

        Args:
            name: Name used to identify the requested file, artifact, or item.
            timestamp: Timestamp used by the operation described above.

        Returns:
            Path returned by ``timestamped_run``.
        """
        _validate_layout_component(name, "run name")
        created_at = timestamp or datetime.now()
        timestamp_text = created_at.strftime("%Y%m%d_%H%M%S_%f")
        return self.root / f"{timestamp_text}_{name}"

    def experiment_runs(self) -> Path:
        """Return the root directory for experiment-run artifacts.

        Returns:
            Path returned by ``experiment_runs``.
        """
        return self.root / "experiment_runs"

    def experiment_run(self, experiment_run_id: str) -> Path:
        """Resolve one named experiment-run directory.

        Args:
            experiment_run_id: Safe identifier assigned to the experiment run.

        Returns:
            The directory holding that experiment run.
        """
        return self.experiment_runs() / _validate_layout_component(
            experiment_run_id, "experiment run id"
        )

    def gpu_experiment_run(self, experiment_run_id: str) -> ExperimentRunArtifactLayout:
        """Resolve the established GPU experiment run path through the artifact layout.

        Args:
            experiment_run_id: Text or path value identifying the experiment run id.

        Returns:
            Result of resolve the established GPU experiment run path through the artifact layout.
        """
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", experiment_run_id):
            raise ValueError(f"unsafe experiment run id: {experiment_run_id!r}")
        return ExperimentRunArtifactLayout(self.root / "gpu_experiment_runs" / experiment_run_id)

    def evaluation(self, evaluation_id: str) -> Path:
        """Resolve the directory for one evaluation result.

        Args:
            evaluation_id: Safe evaluation identifier.

        Returns:
            The evaluation artifact directory.
        """
        return self.root / "evaluation" / _validate_layout_component(evaluation_id, "evaluation id")

    def research(self) -> Path:
        """Return the directory reserved for research artifacts.

        Returns:
            Path returned by ``research``.
        """
        return self.root / "research"

    def reports(self) -> Path:
        """Return the directory reserved for generated reports.

        Returns:
            Path returned by ``reports``.
        """
        return self.root / "reports"


@dataclass(frozen=True, slots=True)
class ExperimentRunArtifactLayout:
    """Named artifact paths for an experiment run, preserving its established on-disk layout."""

    root: Path

    @property
    def manifest(self) -> Path:
        """Return the path to the experiment-run manifest.

        Returns:
            Path returned by ``manifest``.
        """
        return self.root / "experiment_run.json"

    @property
    def controller_lock(self) -> Path:
        """Return the controller lock-file path.

        Returns:
            Path returned by ``controller_lock``.
        """
        return self.root / "controller.lock"

    @property
    def logs(self) -> Path:
        """Return the directory containing controller and worker logs.

        Returns:
            Path returned by ``logs``.
        """
        return self.root / "logs"

    @property
    def worker_logs(self) -> Path:
        """Return the directory containing per-worker logs.

        Returns:
            Path returned by ``worker_logs``.
        """
        return self.logs / "workers"

    @property
    def failure_logs(self) -> Path:
        """Return the directory containing failed-attempt logs.

        Returns:
            Path returned by ``failure_logs``.
        """
        return self.logs / "failures"

    @property
    def runs(self) -> Path:
        """Return the directory containing run-level outputs.

        Returns:
            Path returned by ``runs``.
        """
        return self.root / "runs"

    @property
    def markers(self) -> Path:
        """Return the directory containing completion markers.

        Returns:
            Path returned by ``markers``.
        """
        return self.root / "markers"

    @property
    def reports(self) -> Path:
        """Return the directory containing experiment reports.

        Returns:
            Path returned by ``reports``.
        """
        return self.root / "reports"

    @property
    def source_snapshot(self) -> Path:
        """Return the path to the archived source snapshot.

        Returns:
            Path returned by ``source_snapshot``.
        """
        return self.root / "source_snapshot.zip"

    @property
    def queue(self) -> Path:
        """Return the path to the append-only work queue.

        Returns:
            Path returned by ``queue``.
        """
        return self.root / "queue.jsonl"

    def report(self, name: str) -> Path:
        """Resolve a named report file below the reports directory.

        Args:
            name: Safe report filename.

        Returns:
            The report path.
        """
        return self._named_file(self.reports, name, "report")

    def root_file(self, name: str) -> Path:
        """Resolve a named artifact file directly below the run root.

        Args:
            name: Safe artifact filename.

        Returns:
            The artifact path.
        """
        return self._named_file(self.root, name, "artifact")

    def log(self, name: str) -> Path:
        """Resolve a named controller log below the logs directory.

        Args:
            name: Safe log filename.

        Returns:
            The log path.
        """
        return self._named_file(self.logs, name, "log")

    def worker_log(self, run_key: str, attempt: int) -> Path:
        """Resolve the log for one worker attempt.

        Args:
            run_key: Stable key for the work item.
            attempt: Positive attempt number.

        Returns:
            The worker log path.
        """
        self._validate_run_key(run_key)
        self._validate_attempt(attempt)
        return self.worker_logs / f"{run_key}__attempt{attempt}.log"

    def attempt(self, run_key: str, attempt: int) -> Path:
        """Resolve the artifact directory for one run attempt.

        Args:
            run_key: Stable key for the work item.
            attempt: Positive attempt number.

        Returns:
            The attempt directory.
        """
        self._validate_run_key(run_key)
        self._validate_attempt(attempt)
        return self.runs / "attempts" / run_key / f"attempt{attempt}"

    def run_attempts(self, run_key: str) -> Path:
        """Return the directory containing attempts for one work item.

        Args:
            run_key: Stable key for the work item.

        Returns:
            The work item's attempt directory.
        """
        self._validate_run_key(run_key)
        return self.runs / "attempts" / run_key

    def completion_marker(self, run_key: str) -> Path:
        """Resolve the completion marker for one work item.

        Args:
            run_key: Stable key for the work item.

        Returns:
            The completion marker path.
        """
        self._validate_run_key(run_key)
        return self.markers / f"{run_key}.done"

    def bootstrap_checkpoint(self, run_key: str) -> Path:
        """Resolve the bootstrap checkpoint path for one work item.

        Args:
            run_key: Stable key for the work item.

        Returns:
            The checkpoint archive path.
        """
        self._validate_run_key(run_key)
        return self.root / "bootstrap_checkpoints" / f"{run_key}.zip"

    def resolve_recorded_path(self, value: str | Path) -> Path:
        """Resolve a manifest path without allowing it to escape the experiment run root.

        Args:
            value: Value to process.

        Returns:
            Path returned by ``resolve_recorded_path``.
        """
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved_root = self.root.resolve()
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_root):
            raise ValueError("recorded experiment run path escapes its experiment run directory")
        return resolved_candidate

    def recovery_checkpoint(self, value: str | Path) -> Path:
        """Resolve a recorded checkpoint only when it remains inside this experiment run.

        Args:
            value: Value to process.

        Returns:
            Path returned by ``recovery_checkpoint``.
        """
        try:
            return self.resolve_recorded_path(value)
        except ValueError:
            raise ValueError(
                "experiment run checkpoint path escapes its experiment run directory"
            ) from None

    def ensure_controller_directories(self) -> None:
        """Create the directories required by the experiment-run controller."""
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
        """Validate run key.

        Args:
            run_key: Text or path value identifying the run key.
        """
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,150}", run_key):
            raise ValueError(f"unsafe experiment run key: {run_key!r}")

    @staticmethod
    def _validate_attempt(attempt: int) -> None:
        """Validate attempt.

        Args:
            attempt: Numeric value used for the attempt.
        """
        if type(attempt) is not int or attempt < 1:
            raise ValueError("experiment run attempt must be a positive integer")

    @staticmethod
    def _named_file(directory: Path, name: str, kind: str) -> Path:
        """Process file.

        Args:
            directory: Text or path value identifying the directory.
            name: Name used to identify the requested file, artifact, or item.
            kind: Text or path value identifying the kind.

        Returns:
            Path returned by ``_named_file``.
        """
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError(f"experiment run {kind} name must be a file name")
        return directory / name
