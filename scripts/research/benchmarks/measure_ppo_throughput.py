"""Measure PPO training throughput (FPS) on the read-only env bundle.

This probe resolves the requested variant/config and applies the same hardware
scaling function as production training. It reports both configured and
effective SB3 values so a probe is not mistaken for a production match when
the requested profile differs.

``total_timesteps`` is configurable and defaults to a longer (not short-probe)
amount of work. It is not a training-quality run -- it only measures throughput.

This is a PPO-core benchmark. It resolves the same PPO configuration and uses
the production bundle environment factory, but does not install production
dashboard, checkpoint, or evaluation callbacks. Callback and checkpoint timing
remain unmeasured, so this is not an end-to-end campaign benchmark.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, nullcontext
from functools import partial
from pathlib import Path
from typing import Any, TypedDict, cast

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
from gymnasium import spaces  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from scripts.research.benchmarks.measure_env_memory import (  # noqa: E402
    _cgroup_memory_bytes,
    _load_train_slice,
    _tree_pss_mib,
)  # noqa: E402

from compute.environment.device import scale_training_cfg  # noqa: E402
from compute.environment.precision import configure_cuda_for_training  # noqa: E402
from compute.slurm.resources import (  # noqa: E402
    allocation_cgroup_file,
    descendant_pids,
    process_tree_cpu_usec,
    read_process_table,
)  # noqa: E402
from learning.rl.agent import build_agent  # noqa: E402
from simulation.environment.bundles import build_env_bundle  # noqa: E402
from simulation.environment.spec import EnvSpec  # noqa: E402
from simulation.environment.worker import make_bundle_env  # noqa: E402
from training.configuration.cli import load_merged_config  # noqa: E402
from training.runner.seed import _setup_rngs  # noqa: E402
from training.setup.environments import strategy_from_cfg  # noqa: E402


class _StepTiming(TypedDict):
    seconds: float
    steps: int
    observation_construction_seconds: float
    observation_construction_calls: int
    sampled_step_ms: list[float]
    sampled_decision_indices: list[int]


class _StepTimingWrapper(gym.Wrapper[Any, Any, Any, Any]):
    """Collect per-environment step duration for a diagnostic probe."""

    def __init__(self, env: gym.Env[Any, Any]) -> None:
        super().__init__(env)
        self._step_seconds = 0.0
        self._step_count = 0
        self._observation_construction_seconds = 0.0
        self._observation_construction_calls = 0
        self._sampled_step_ms: list[float] = []
        self._sampled_decision_indices: list[int] = []
        observation_builder = getattr(env.unwrapped, "_get_observation", None)
        if callable(observation_builder):

            def timed_observation_builder(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                try:
                    return observation_builder(*args, **kwargs)
                finally:
                    self._observation_construction_seconds += time.perf_counter() - started
                    self._observation_construction_calls += 1

            setattr(env.unwrapped, "_get_observation", timed_observation_builder)

    def step(self, action: Any) -> Any:
        started = time.perf_counter()
        decision_index = getattr(self.env.unwrapped, "step_idx", None)
        try:
            return self.env.step(action)
        finally:
            elapsed = time.perf_counter() - started
            self._step_seconds += elapsed
            self._step_count += 1
            # Systematic sampling keeps profiling memory bounded and avoids
            # collecting a large Python object per transition on long runs.
            if self._step_count % 8 == 0:
                self._sampled_step_ms.append(elapsed * 1000.0)
                if decision_index is not None:
                    self._sampled_decision_indices.append(int(decision_index))

    def get_step_timing(self) -> _StepTiming:
        return {
            "seconds": self._step_seconds,
            "steps": self._step_count,
            "observation_construction_seconds": self._observation_construction_seconds,
            "observation_construction_calls": self._observation_construction_calls,
            "sampled_step_ms": self._sampled_step_ms,
            "sampled_decision_indices": self._sampled_decision_indices,
        }


def _timed_env_from_factory(env_factory: Any) -> _StepTimingWrapper:
    return _StepTimingWrapper(env_factory())


def _json_default(value: Any) -> Any:
    """Convert NumPy scalar metadata to JSON-native Python values."""
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _sample_summary(samples: list[float], *, scale: float = 1.0) -> dict[str, float | int | None]:
    """Summarize bounded diagnostic samples without implying full-run coverage."""
    if not samples:
        return {"sample_count": 0, "total": 0.0, "p50": None, "p95": None}
    values = np.asarray(samples, dtype=np.float64) * scale
    return {
        "sample_count": int(values.size),
        "total": float(values.sum()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
    }


class _NvidiaSmiSampler:
    """Collect coarse device telemetry without treating memory use as utilization."""

    _FIELDS = (
        "utilization.gpu",
        "utilization.memory",
        "memory.used",
        "memory.total",
        "power.draw",
        "clocks.current.sm",
        "clocks.current.memory",
    )

    def __init__(
        self,
        interval_seconds: float = 1.0,
        phase_provider: Callable[[], str] | None = None,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.phase_provider = phase_provider
        self.executable = shutil.which("nvidia-smi")
        self.samples: list[dict[str, float | str]] = []
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.executable is None:
            self.error = "nvidia-smi not found"
            return
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def _sample_loop(self) -> None:
        assert self.executable is not None
        query = ",".join(self._FIELDS)
        visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",")
        device_selector = [f"--id={visible_devices[0]}"] if visible_devices[0] else []
        while not self._stop.is_set():
            try:
                result = subprocess.run(
                    [
                        self.executable,
                        *device_selector,
                        f"--query-gpu={query}",
                        "--format=csv,noheader,nounits",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=max(2.0, self.interval_seconds * 2.0),
                )
                fields = [value.strip() for value in result.stdout.splitlines()[0].split(",")]
                if len(fields) != len(self._FIELDS):
                    raise ValueError(f"unexpected nvidia-smi field count: {fields!r}")
                sample: dict[str, float | str] = {
                    field: float(value)
                    for field, value in zip(self._FIELDS, fields, strict=True)
                    if value.lower() not in {"n/a", "[not supported]"}
                }
                if self.phase_provider is not None:
                    sample["phase"] = self.phase_provider()
                self.samples.append(sample)
            except (IndexError, OSError, subprocess.SubprocessError, ValueError) as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                return
            self._stop.wait(self.interval_seconds)

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if not self.samples:
            return {
                "available": False,
                "sample_count": 0,
                "sampling_interval_seconds": self.interval_seconds,
                "reason": self.error or "no samples collected",
                "sm_active_pct": None,
                "dram_bandwidth": None,
            }

        def summarize(samples: list[dict[str, float | str]]) -> dict[str, Any]:
            return {
                field: _sample_summary(
                    [float(sample[field]) for sample in samples if field in sample]
                )
                for field in self._FIELDS
            }

        by_phase: dict[str, list[dict[str, float | str]]] = {}
        for sample in self.samples:
            by_phase.setdefault(str(sample.get("phase", "unattributed")), []).append(sample)
        summaries = summarize(self.samples)
        return {
            "available": True,
            "source": "nvidia-smi coarse telemetry",
            "sample_count": len(self.samples),
            "sampling_interval_seconds": self.interval_seconds,
            "fields": summaries,
            "fields_by_phase": {phase: summarize(samples) for phase, samples in by_phase.items()},
            "sm_active_pct": None,
            "dram_bandwidth": None,
            "limitations": (
                "utilization.gpu is coarse device utilization, not SM-active or occupancy; "
                "memory.used is capacity usage, not DRAM bandwidth."
            ),
        }


class _ProcessTreeSampler:
    """Sample process/thread run and wait states during profiled phases."""

    def __init__(self, root_pid: int, interval_seconds: float = 1.0) -> None:
        self.root_pid = root_pid
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self.error: str | None = None
        self._phase = "startup"
        self._phase_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        with self._phase_lock:
            previous = self._phase
            self._phase = name
        try:
            yield
        finally:
            with self._phase_lock:
                self._phase = previous

    def current_phase(self) -> str:
        with self._phase_lock:
            return self._phase

    def start(self) -> None:
        self._thread = threading.Thread(target=self._sample_guarded, daemon=True)
        self._thread.start()

    def _sample_guarded(self) -> None:
        try:
            self._sample_loop()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _thread_snapshot(tid: int, task_path: Path) -> dict[str, Any] | None:
        try:
            stat_text = (task_path / "stat").read_text()
            stat_fields = stat_text[stat_text.rfind(")") + 2 :].split()
            status_lines = (task_path / "status").read_text().splitlines()
        except OSError:
            return None
        if len(stat_fields) <= 12:
            return None
        counters = {
            line.split(":", maxsplit=1)[0]: int(line.split()[1])
            for line in status_lines
            if line.startswith(("voluntary_ctxt_switches:", "nonvoluntary_ctxt_switches:"))
        }
        try:
            affinity_size = len(os.sched_getaffinity(tid))
        except (AttributeError, OSError, ProcessLookupError):
            affinity_size = 0
        try:
            wchan = (task_path / "wchan").read_text().strip()
        except OSError:
            wchan = "unknown"
        return {
            "state": stat_fields[0],
            "cpu_ticks": int(stat_fields[11]) + int(stat_fields[12]),
            "minor_faults": int(stat_fields[7]),
            "major_faults": int(stat_fields[9]),
            "voluntary_ctxt_switches": counters.get("voluntary_ctxt_switches", 0),
            "nonvoluntary_ctxt_switches": counters.get("nonvoluntary_ctxt_switches", 0),
            "affinity_size": affinity_size,
            "wchan": wchan,
        }

    def _snapshot(self) -> dict[int, dict[str, Any]]:
        parents = read_process_table()
        process_ids = descendant_pids([self.root_pid], parents)
        threads: dict[int, dict[str, Any]] = {}
        sampler_tid = threading.get_native_id()
        for pid in process_ids:
            try:
                tasks = list(Path(f"/proc/{pid}/task").iterdir())
            except OSError:
                continue
            for task in tasks:
                if not task.name.isdigit() or int(task.name) == sampler_tid:
                    continue
                snapshot = self._thread_snapshot(int(task.name), task)
                if snapshot is not None:
                    threads[int(task.name)] = snapshot
        return threads

    def _sample_loop(self) -> None:
        previous = self._snapshot()
        previous_time = time.monotonic()
        ticks_per_second = int(os.sysconf("SC_CLK_TCK"))
        while not self._stop.wait(self.interval_seconds):
            now = time.monotonic()
            current = self._snapshot()
            with self._phase_lock:
                phase_name = self._phase
            elapsed = max(now - previous_time, 1e-9)
            state_counts = Counter(item["state"] for item in current.values())
            affinity_counts = Counter(
                str(item["affinity_size"]) for item in current.values() if item["affinity_size"]
            )
            wchan_counts = Counter(
                item["wchan"]
                for item in current.values()
                if item["state"] in {"S", "D"} and item["wchan"] not in {"0", "unknown"}
            )
            cpu_ticks = 0
            minor_faults = 0
            major_faults = 0
            voluntary_switches = 0
            involuntary_switches = 0
            for tid, item in current.items():
                old = previous.get(tid, {})
                cpu_ticks += max(item["cpu_ticks"] - old.get("cpu_ticks", item["cpu_ticks"]), 0)
                minor_faults += max(
                    item["minor_faults"] - old.get("minor_faults", item["minor_faults"]), 0
                )
                major_faults += max(
                    item["major_faults"] - old.get("major_faults", item["major_faults"]), 0
                )
                voluntary_switches += max(
                    item["voluntary_ctxt_switches"]
                    - old.get("voluntary_ctxt_switches", item["voluntary_ctxt_switches"]),
                    0,
                )
                involuntary_switches += max(
                    item["nonvoluntary_ctxt_switches"]
                    - old.get("nonvoluntary_ctxt_switches", item["nonvoluntary_ctxt_switches"]),
                    0,
                )
            try:
                load_1m = float(Path("/proc/loadavg").read_text().split()[0])
            except (OSError, ValueError):
                load_1m = None
            self.samples.append(
                {
                    "phase": phase_name,
                    "thread_count": len(current),
                    "state_counts": dict(state_counts),
                    "affinity_size_counts": dict(affinity_counts),
                    "sleep_wchan_counts": dict(wchan_counts.most_common(8)),
                    "busy_cpu_cores": cpu_ticks / ticks_per_second / elapsed,
                    "minor_page_faults": minor_faults,
                    "major_page_faults": major_faults,
                    "voluntary_context_switches_per_second": voluntary_switches / elapsed,
                    "involuntary_context_switches_per_second": involuntary_switches / elapsed,
                    "host_load_average_1m": load_1m,
                }
            )
            previous = current
            previous_time = now

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for sample in self.samples:
            grouped.setdefault(str(sample["phase"]), []).append(sample)
        phase_reports: dict[str, Any] = {}
        for phase_name, samples in grouped.items():
            state_totals: Counter[str] = Counter()
            wchan_totals: Counter[str] = Counter()
            affinity_totals: Counter[str] = Counter()
            host_load_values = [
                float(sample["host_load_average_1m"])
                for sample in samples
                if sample["host_load_average_1m"] is not None
            ]
            for sample in samples:
                state_totals.update(sample["state_counts"])
                wchan_totals.update(sample["sleep_wchan_counts"])
                affinity_totals.update(sample["affinity_size_counts"])
            phase_reports[phase_name] = {
                "sample_count": len(samples),
                "mean_thread_count": float(np.mean([s["thread_count"] for s in samples])),
                "mean_busy_cpu_cores": float(np.mean([s["busy_cpu_cores"] for s in samples])),
                "mean_state_counts_per_sample": {
                    state: value / len(samples) for state, value in state_totals.items()
                },
                "mean_affinity_size_counts_per_sample": {
                    size: value / len(samples) for size, value in affinity_totals.items()
                },
                "sampled_sleep_wait_channels": dict(wchan_totals.most_common(8)),
                "minor_page_faults": int(sum(s["minor_page_faults"] for s in samples)),
                "major_page_faults": int(sum(s["major_page_faults"] for s in samples)),
                "voluntary_context_switches_per_second": float(
                    np.mean([s["voluntary_context_switches_per_second"] for s in samples])
                ),
                "involuntary_context_switches_per_second": float(
                    np.mean([s["involuntary_context_switches_per_second"] for s in samples])
                ),
                "mean_host_load_average_1m": (
                    float(np.mean(host_load_values)) if host_load_values else None
                ),
            }
        return {
            "available": bool(self.samples),
            "reason": self.error,
            "source": "/proc thread state/cpu/context-switch sampling",
            "sampling_interval_seconds": self.interval_seconds,
            "sample_count": len(self.samples),
            "phases": phase_reports,
            "ipc_bytes": None,
            "ipc_bytes_reason": "worker pipe byte counters are not exposed by this sampler",
        }


def _process_tree_cpu_seconds() -> float:
    """Return cumulative CPU time for this trainer and its live descendants."""
    process_ids = descendant_pids([os.getpid()], read_process_table())
    return process_tree_cpu_usec(process_ids) / 1_000_000.0


def _working_tree_patch_identity(repository_root: Path) -> dict[str, Any]:
    """Fingerprint tracked edits and untracked source files, excluding run outputs."""
    tracked_diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    ).stdout
    untracked_paths = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    source_suffixes = {".py", ".yaml", ".yml", ".sh", ".sbatch", ".md"}
    untracked_source_hashes: dict[str, str] = {}
    for raw_path in untracked_paths:
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        if relative.suffix.lower() not in source_suffixes:
            continue
        if "measurements" in relative.parts or relative.name.startswith("slurm-"):
            continue
        source_path = repository_root / relative
        if source_path.is_file():
            untracked_source_hashes[relative.as_posix()] = hashlib.sha256(
                source_path.read_bytes()
            ).hexdigest()

    patch_digest = hashlib.sha256()
    patch_digest.update(b"tracked-diff-head\0")
    patch_digest.update(tracked_diff)
    for untracked_relative, digest in sorted(untracked_source_hashes.items()):
        patch_digest.update(b"\0untracked-source\0")
        patch_digest.update(untracked_relative.encode("utf-8"))
        patch_digest.update(b"\0")
        patch_digest.update(digest.encode("ascii"))

    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        "working_tree_dirty": bool(status.strip()),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "untracked_source_sha256": untracked_source_hashes,
        "patch_identity_sha256": patch_digest.hexdigest(),
        "excluded_generated_outputs": ["measurements/**", "slurm-*.out"],
    }


def _allocation_cgroup_metrics() -> dict[str, Any]:
    """Read allocation-scoped CPU and memory limits/pressure when available."""
    values: dict[str, str] = {}
    for name in (
        "cpu.max",
        "cpuset.cpus.effective",
        "memory.current",
        "memory.peak",
        "memory.events",
        "memory.pressure",
        "cpu.pressure",
    ):
        path = allocation_cgroup_file(name)
        if path is not None:
            try:
                values[name] = path.read_text().strip()
            except OSError:
                continue
    cpu_quota_cores: float | None = None
    quota = values.get("cpu.max", "").split()
    if len(quota) == 2 and quota[0] != "max":
        try:
            cpu_quota_cores = int(quota[0]) / int(quota[1])
        except (ValueError, ZeroDivisionError):
            cpu_quota_cores = None
    cpuset_count: int | None = None
    cpuset = values.get("cpuset.cpus.effective")
    if cpuset:
        try:
            count = 0
            for part in cpuset.split(","):
                bounds = part.split("-", maxsplit=1)
                count += int(bounds[-1]) - int(bounds[0]) + 1
            cpuset_count = count
        except ValueError:
            cpuset_count = None
    return {
        "raw": values,
        "cpu_quota_cores": cpu_quota_cores,
        "cpuset_cpu_count": cpuset_count,
        "allocated_cpus_env": int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) or None,
    }


@contextmanager
def _time_method_calls(
    instance: Any,
    method_name: str,
    samples: list[float],
    *,
    profile: bool = False,
    range_name: str | None = None,
    cpu_samples: list[float] | None = None,
    cuda_event_pairs: list[tuple[Any, Any]] | None = None,
    process_sampler: _ProcessTreeSampler | None = None,
) -> Iterator[None]:
    """Time a class method and optionally annotate its CPU/CUDA timeline."""
    owner = type(instance)
    original_method = getattr(owner, method_name)

    def timed_method(target: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        cpu_started = _process_tree_cpu_seconds() if profile and cpu_samples is not None else 0.0
        torch_module: Any = None
        event_pair: tuple[Any, Any] | None = None
        nvtx_pushed = False
        if profile and range_name is not None:
            try:
                import torch as torch_module

                if torch_module.cuda.is_available():
                    torch_module.cuda.nvtx.range_push(range_name)
                    nvtx_pushed = True
                    if cuda_event_pairs is not None:
                        start_event = torch_module.cuda.Event(enable_timing=True)
                        end_event = torch_module.cuda.Event(enable_timing=True)
                        start_event.record()
                        event_pair = (start_event, end_event)
            except (ImportError, RuntimeError):
                torch_module = None
        try:
            phase_context = (
                process_sampler.phase(range_name or method_name)
                if profile and process_sampler is not None
                else nullcontext()
            )
            with phase_context:
                return original_method(target, *args, **kwargs)
        finally:
            if event_pair is not None:
                event_pair[1].record()
                assert cuda_event_pairs is not None
                cuda_event_pairs.append(event_pair)
            if nvtx_pushed and torch_module is not None:
                torch_module.cuda.nvtx.range_pop()
            samples.append(time.perf_counter() - started)
            if profile and cpu_samples is not None:
                cpu_samples.append(max(_process_tree_cpu_seconds() - cpu_started, 0.0))

    setattr(owner, method_name, timed_method)
    try:
        yield
    finally:
        setattr(owner, method_name, original_method)


@contextmanager
def _time_callable(
    owner: Any,
    attribute: str,
    samples: list[float],
    *,
    range_name: str,
    process_sampler: _ProcessTreeSampler | None = None,
) -> Iterator[None]:
    """Time a module function or bound callable and annotate its diagnostic range."""
    original = getattr(owner, attribute)

    def timed_callable(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        torch_module: Any = None
        nvtx_pushed = False
        try:
            import torch as torch_module

            if torch_module.cuda.is_available():
                torch_module.cuda.nvtx.range_push(range_name)
                nvtx_pushed = True
        except (ImportError, RuntimeError):
            torch_module = None
        phase_context = (
            process_sampler.phase(range_name) if process_sampler is not None else nullcontext()
        )
        try:
            with phase_context:
                return original(*args, **kwargs)
        finally:
            if nvtx_pushed and torch_module is not None:
                torch_module.cuda.nvtx.range_pop()
            samples.append(time.perf_counter() - started)

    setattr(owner, attribute, timed_callable)
    try:
        yield
    finally:
        setattr(owner, attribute, original)


@contextmanager
def _time_tensor_backward(
    torch_module: Any,
    samples: list[float],
    process_sampler: _ProcessTreeSampler | None,
) -> Iterator[None]:
    """Measure host call time and add an NVTX range around each backward call."""
    original = torch_module.Tensor.backward

    def timed_backward(tensor: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        nvtx_pushed = False
        try:
            if torch_module.cuda.is_available():
                torch_module.cuda.nvtx.range_push("ppo.backward")
                nvtx_pushed = True
        except RuntimeError:
            pass
        phase_context = (
            process_sampler.phase("ppo.backward") if process_sampler is not None else nullcontext()
        )
        try:
            with phase_context:
                return original(tensor, *args, **kwargs)
        finally:
            if nvtx_pushed:
                torch_module.cuda.nvtx.range_pop()
            samples.append(time.perf_counter() - started)

    torch_module.Tensor.backward = timed_backward
    try:
        yield
    finally:
        torch_module.Tensor.backward = original


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n-envs",
        type=int,
        default=None,
        help="Override the resolved/scaled environment count for a separate profile.",
    )
    parser.add_argument(
        "--rollout-steps-per-env",
        type=int,
        default=None,
        help="Override rollout length per environment; this changes PPO update geometry.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override the effective PPO minibatch size after hardware scaling.",
    )
    parser.add_argument(
        "--torch-compile-mode",
        choices=("default", "reduce-overhead", "max-autotune"),
        default=None,
        help="Compile the PPO policy for an isolated learner benchmark.",
    )
    parser.add_argument(
        "--matmul-precision",
        choices=("highest", "high", "medium"),
        default=None,
        help="Override CUDA float32 matmul precision after production CUDA setup.",
    )
    parser.add_argument(
        "--measure-env-steps",
        action="store_true",
        help="Time TradingEnv.step calls and report per-shard environment time.",
    )
    parser.add_argument(
        "--profile-phases",
        action="store_true",
        help=(
            "Enable diagnostic CPU phase timings and CUDA NVTX/event annotations. "
            "This adds measurement overhead; keep profiled runs separate from baseline FPS runs."
        ),
    )
    parser.add_argument(
        "--total-timesteps",
        type=int,
        default=None,
        help="Total env steps (default: resolved config ppo.total_timesteps).",
    )
    parser.add_argument(
        "--warmup-rollouts",
        type=int,
        default=0,
        help=(
            "Initial complete PPO rollouts to exclude from the warmed PPO-core rate. "
            "They still count toward total training transitions."
        ),
    )
    parser.add_argument("--config", type=Path, default=None, help="Production base config.")
    parser.add_argument("--seed", type=int, default=42, help="Training RNG seed (default: 42).")
    parser.add_argument(
        "--overrides",
        nargs="*",
        default=None,
        help="key=value overrides, applied after strategy config merge.",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default="cpu",
        help="Device to train on; CUDA is required for the production GPU estimate.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--variant",
        default=None,
        help=(
            "Measure an experiments.yaml variant: its base config, overrides, algo and "
            "arch are taken from training.configuration.variant_resolution. Requires --bundle-dir."
        ),
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=None,
        help=(
            "Reuse an already-built bundle at this path instead of rebuilding one. "
            "Rebuilding loads the full train-split frames and needs ~512 GiB."
        ),
    )
    parser.add_argument(
        "--update-semaphore-dir",
        type=Path,
        default=None,
        help="Optional shared lock directory for an isolated multi-trainer update-scheduling probe.",
    )
    parser.add_argument(
        "--update-semaphore-slots",
        type=int,
        default=0,
        help="Maximum concurrent PPO train() sections when using --update-semaphore-dir.",
    )
    return parser.parse_args()


def _acquire_update_slot(directory: Path, slots: int) -> Any:
    """Acquire one cross-process update slot; caller closes the returned handle."""
    import fcntl

    directory.mkdir(parents=True, exist_ok=True)
    while True:
        for index in range(slots):
            handle = (directory / f"slot-{index}.lock").open("a+")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                continue
            return handle
        time.sleep(0.01)


def _prepare_bundle(
    bundle_dir: Path | None,
    variant: str | None = None,
    config_path: Path | None = None,
    overrides: list[str] | None = None,
) -> tuple[Any, Path, str, str]:
    """Return resolved config and bundle identity for the production backend.

    Building a bundle from scratch loads the whole train-split frame set (which
    peaked around 473 GiB and OOMs below 256 GiB), so a throughput probe that
    only needs the training loop can point at an already-built bundle instead.
    """
    strategy = "baseline"
    algo, arch = "ppo", "tcn"
    resolved_overrides = list(overrides or [])
    if variant is not None:
        from training.configuration.variant_resolution import resolve_variant

        resolved = resolve_variant(variant)
        if bundle_dir is None:
            raise SystemExit(
                "--variant needs --bundle-dir: rebuilding a bundle is not variant-aware"
            )
        config_path = Path(resolved["base_config"])
        strategy = str(resolved["strategy"])
        algo, arch = str(resolved["algo"]), str(resolved["arch"])
        resolved_overrides = [*resolved["overrides"], *resolved_overrides]

    if config_path is None and bundle_dir is None and not resolved_overrides:
        cfg, bars, features, tickbook = _load_train_slice(None)
        strategy_obj = strategy_from_cfg(cfg)[0]
        bundle_path = build_env_bundle(
            cfg.data.cache_dir,
            bars,
            features,
            cfg,
            raw_columns=list(strategy_obj.raw_columns),
            feature_config_hash="phase4-share-ppo",
            tickbook=tickbook,
            pre_ny_by_date=None,
        )
        del bars, features, tickbook
        gc.collect()
        return (
            cfg,
            bundle_path,
            algo,
            arch,
        )

    if bundle_dir is None:
        raise SystemExit("custom configs/overrides require --bundle-dir")
    config_name = str(config_path or "config/base/default.yaml")
    # This is the same merge routine used by the production CLI: base config,
    # strategy overlay, then explicit overrides.
    cfg = load_merged_config(
        argparse.Namespace(
            config=config_name,
            strategy=strategy,
            variant=None,
            overrides=resolved_overrides,
        )
    )
    if algo != "ppo":
        raise SystemExit(f"PPO throughput probe does not support algo={algo!r}")
    if variant is None:
        arch = str(cfg.agent.get("arch", arch))
    return (
        cfg,
        bundle_dir,
        algo,
        arch,
    )


def _apply_profile_overrides(
    cfg: Any,
    *,
    n_envs: int | None,
    rollout_steps_per_env: int | None,
    batch_size: int | None = None,
) -> None:
    """Apply explicit benchmark overrides after production hardware scaling."""
    if n_envs is not None:
        cfg.env.n_envs = n_envs
    if rollout_steps_per_env is not None:
        cfg.ppo.n_steps = int(cfg.env.n_envs) * rollout_steps_per_env
    if batch_size is not None:
        cfg.ppo.batch_size = batch_size


def _scale_profile_config(cfg: Any, device: Any, arch: str) -> None:
    """Use production's exact-geometry contract when scaling a benchmark config."""
    requested_n_envs = int(cfg.env.n_envs)
    exact_n_envs = bool(cfg.get("quality_execution", {}).get("exact_n_envs", False))
    scale_training_cfg(
        cfg,
        device,
        arch,
        preserve_ppo_geometry=exact_n_envs,
    )
    if exact_n_envs and int(cfg.env.n_envs) != requested_n_envs:
        raise ValueError(
            "exact_n_envs benchmark config changed environment count during scaling: "
            f"requested {requested_n_envs}, got {cfg.env.n_envs}"
        )


def _validate_high_throughput_runtime_identity(
    cfg: Any,
    model: Any,
    vec_env: Any,
    parent_env: Any,
    config_path: Path | None,
) -> dict[str, Any] | None:
    """Fail closed if the high-throughput overlay does not build Variant E."""
    if config_path is None or config_path.name != "thesis_mtf_shared_tcn_2m_high_throughput.yaml":
        return None

    from decisioning.thesis import THESIS_CATEGORY_COUNT

    observations = parent_env.observation_space.spaces
    policy_name = type(model.policy).__name__
    expected_backend_class = {
        "sharded_bundle": "ShardedBundleVecEnv",
        "subproc": "SubprocVecEnv",
    }.get(str(cfg.env.vector_backend))
    checks = {
        "variant_e_encoder": str(cfg.agent.arch) == "mtf_shared_tcn_reasoning",
        "thesis_conditioned_distribution": (
            str(cfg.ppo.policy_distribution) == "thesis_conditioned_v1"
        ),
        "thesis_actions_enabled": bool(cfg.env.thesis_actions),
        "64_logical_envs": int(model.n_envs) == 64 and int(vec_env.num_envs) == 64,
        "256_steps_per_env": int(model.n_steps) == 256,
        "4096_minibatch": int(model.batch_size) == 4096,
        "15_ppo_epochs": int(model.n_epochs) == 15,
        "conditioned_policy": policy_name == "ThesisConditionedClampedStdMultiInputPolicy",
        "109_way_thesis_mask": tuple(observations["thesis_mask"].shape) == (THESIS_CATEGORY_COUNT,),
        "configured_vector_backend": (
            expected_backend_class is not None and type(vec_env).__name__ == expected_backend_class
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(
            "high-throughput config/runtime identity check failed: " + ", ".join(failed)
        )
    return {
        "passed": True,
        "checks": checks,
        "policy_class": policy_name,
        "vector_backend": type(vec_env).__name__,
        "logical_envs": int(model.n_envs),
        "rollout_steps_per_env": int(model.n_steps),
        "aggregate_rollout": int(model.n_envs * model.n_steps),
        "batch_size": int(model.batch_size),
        "ppo_epochs": int(model.n_epochs),
        "thesis_category_count": THESIS_CATEGORY_COUNT,
    }


def _train_probe(
    n_envs: int | None,
    rollout_steps_per_env: int | None,
    total_timesteps: int | None,
    device: str,
    output: Path,
    bundle_dir: Path | None = None,
    variant: str | None = None,
    config_path: Path | None = None,
    overrides: list[str] | None = None,
    seed: int = 42,
    batch_size: int | None = None,
    torch_compile_mode: str | None = None,
    matmul_precision: str | None = None,
    measure_env_steps: bool = False,
    update_semaphore_dir: Path | None = None,
    update_semaphore_slots: int = 0,
    warmup_rollouts: int = 0,
    profile_phases: bool = False,
) -> dict[str, Any]:
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is false")

    cfg, bundle_path, algo, arch = _prepare_bundle(bundle_dir, variant, config_path, overrides)
    # This probe always instantiates the shared-bundle backend; make the
    # hardware scaler use the same worker memory estimate as that backend.
    cfg.env.data_source = "bundle"
    configure_cuda_for_training(
        cudnn_benchmark=bool(cfg.get("compute", {}).get("cudnn_benchmark", True))
    )
    _scale_profile_config(cfg, torch.device(device), arch)
    if matmul_precision is not None:
        torch.set_float32_matmul_precision(matmul_precision)
    _apply_profile_overrides(
        cfg,
        n_envs=n_envs,
        rollout_steps_per_env=rollout_steps_per_env,
        batch_size=batch_size,
    )
    n_envs = int(cfg.env.n_envs)
    total_timesteps = int(
        total_timesteps if total_timesteps is not None else cfg.ppo.total_timesteps
    )
    spec = EnvSpec.from_cfg(
        cfg,
        algo=algo,
        reward=str(cfg.env.get("reward_mode", "dsr")),
        arch=arch,
        bundle_dir=str(bundle_path),
    )
    cfg_text = OmegaConf.to_yaml(cfg, resolve=True)
    config_sha256 = hashlib.sha256(cfg_text.encode("utf-8")).hexdigest()

    torch.set_num_threads(1)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    _setup_rngs(seed)

    gpu_before: dict[str, int | str] = {}
    if device == "cuda":
        torch.cuda.synchronize()
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        gpu_before = {
            "gpu_name": torch.cuda.get_device_name(),
            "gpu_total_bytes": total_bytes,
            "gpu_free_before_bytes": free_bytes,
        }
        torch.cuda.reset_peak_memory_stats()

    start_bytes = _cgroup_memory_bytes()
    parent_env = make_bundle_env(spec)
    if not isinstance(parent_env.observation_space, spaces.Dict):
        raise TypeError("PPO throughput probe requires a Dict observation space")
    env_fn: Callable[[], gym.Env[Any, Any]] = partial(make_bundle_env, spec)
    if measure_env_steps or profile_phases:
        env_fn = partial(_timed_env_from_factory, env_fn)
    model = build_agent(parent_env, cfg, arch=arch, algo=algo, device=device, env_fn=env_fn)
    vec_env = model.get_env()
    try:
        runtime_identity_validation = _validate_high_throughput_runtime_identity(
            cfg, model, vec_env, parent_env, config_path
        )
    except BaseException:
        vec_env.close()
        parent_env.close()
        raise
    compile_warmup_seconds = 0.0
    if torch_compile_mode is not None:
        if device != "cuda":
            raise ValueError("torch.compile mode probes require --device cuda")
        from stable_baselines3.common.utils import obs_as_tensor

        py_rng_state = random.getstate()
        np_rng_state = np.random.get_state()
        torch_rng_state = torch.get_rng_state()
        cuda_rng_state = torch.cuda.get_rng_state_all()
        compile_started = time.monotonic()
        model.policy = torch.compile(model.policy, mode=torch_compile_mode)
        inference_obs = {
            key: np.broadcast_to(space.sample(), (int(model.n_envs), *(space.shape or ()))).copy()
            for key, space in parent_env.observation_space.spaces.items()
        }
        training_obs = {
            key: np.broadcast_to(
                space.sample(), (int(model.batch_size), *(space.shape or ()))
            ).copy()
            for key, space in parent_env.observation_space.spaces.items()
        }
        inference_obs_tensor = obs_as_tensor(inference_obs, model.device)
        training_obs_tensor = obs_as_tensor(training_obs, model.device)
        sample_count = int(model.batch_size)
        if isinstance(model.action_space, spaces.Discrete):
            sample_actions = torch.zeros(sample_count, dtype=torch.long, device=model.device)
        else:
            action_shape = tuple(model.action_space.shape)
            sample_actions = torch.zeros(
                (sample_count, *action_shape), dtype=torch.float32, device=model.device
            )
        with torch.no_grad():
            model.policy(inference_obs_tensor)
        model.policy.evaluate_actions(training_obs_tensor, sample_actions)
        torch.cuda.synchronize()
        compile_warmup_seconds = time.monotonic() - compile_started
        # Compilation warmup must not advance the benchmark's seeded policy RNG.
        random.setstate(py_rng_state)
        np.random.set_state(np_rng_state)
        torch.set_rng_state(torch_rng_state)
        torch.cuda.set_rng_state_all(cuda_rng_state)
    vector_backend = type(vec_env).__name__
    remotes = getattr(vec_env, "remotes", None)
    physical_worker_count = len(remotes) if remotes is not None else 1
    logical_envs_per_worker = getattr(vec_env, "logical_envs_per_shard", None)
    vecenv_bytes = _cgroup_memory_bytes()

    # n_steps is split by n_envs inside build_agent (n_steps // n_envs per env).
    rollout_steps_per_env = int(model.n_steps)
    nominal_env_steps = int(model.n_envs * model.n_steps)

    # Time PPO's gradient phase separately from the env rollout phase, so the
    # reported FPS can be split into "how fast can the envs step" and "how much
    # of the budget the n_epochs=15 update loop costs". SB3 calls ``self.train()``
    # from inside ``learn()``, so shadowing it on the instance times that phase.
    update_timing = {
        "update_seconds": 0.0,
        "update_compute_seconds": 0.0,
        "update_semaphore_wait_seconds": 0.0,
        "update_calls": 0,
    }
    optimizer_timing = {"optimizer_steps": 0}
    rollout_call_seconds: list[float] = []
    update_call_seconds: list[float] = []
    phase_cpu_seconds: dict[str, list[float]] = {
        "collect_rollouts": [],
        "train": [],
    }
    phase_cuda_event_pairs: dict[str, list[tuple[Any, Any]]] = {
        "collect_rollouts": [],
        "train": [],
    }
    method_wall_seconds: dict[str, list[float]] = {
        "policy_forward": [],
        "policy_evaluate_actions": [],
        "vec_step_async": [],
        "vec_step_wait": [],
        "parent_observation_stack": [],
        "rollout_buffer_add": [],
        "gae": [],
        "backward": [],
        "optimizer_step": [],
        "cuda_synchronize": [],
    }
    original_train = model.train
    original_optimizer_step = model.policy.optimizer.step

    def _counted_optimizer_step(*args: Any, **kwargs: Any) -> Any:
        optimizer_timing["optimizer_steps"] += 1
        return original_optimizer_step(*args, **kwargs)

    model.policy.optimizer.step = _counted_optimizer_step

    def _timed_train(*args: Any, **kwargs: Any) -> Any:
        update_started = time.monotonic()
        slot_handle = (
            _acquire_update_slot(update_semaphore_dir, update_semaphore_slots)
            if update_semaphore_dir is not None and update_semaphore_slots > 0
            else None
        )
        compute_started = time.monotonic()
        cpu_started = _process_tree_cpu_seconds() if profile_phases else 0.0
        event_pair: tuple[Any, Any] | None = None
        nvtx_pushed = False
        if profile_phases and device == "cuda":
            try:
                cuda_api = cast(Any, torch.cuda)
                cuda_api.nvtx.range_push("ppo.train")
                nvtx_pushed = True
                start_event = cuda_api.Event(enable_timing=True)
                end_event = cuda_api.Event(enable_timing=True)
                start_event.record()
                event_pair = (start_event, end_event)
            except RuntimeError:
                event_pair = None
        try:
            phase_context = (
                process_sampler.phase("ppo.train")
                if profile_phases and process_sampler is not None
                else nullcontext()
            )
            with phase_context:
                return original_train(*args, **kwargs)
        finally:
            if event_pair is not None:
                event_pair[1].record()
                phase_cuda_event_pairs["train"].append(event_pair)
            if nvtx_pushed:
                cast(Any, torch.cuda).nvtx.range_pop()
            if device == "cuda":
                torch.cuda.synchronize()
            compute_elapsed = time.monotonic() - compute_started
            if profile_phases:
                phase_cpu_seconds["train"].append(
                    max(_process_tree_cpu_seconds() - cpu_started, 0.0)
                )
            if slot_handle is not None:
                import fcntl

                fcntl.flock(slot_handle.fileno(), fcntl.LOCK_UN)
                slot_handle.close()
            elapsed = time.monotonic() - update_started
            update_timing["update_seconds"] += elapsed
            update_timing["update_compute_seconds"] += compute_elapsed
            update_timing["update_semaphore_wait_seconds"] += max(elapsed - compute_elapsed, 0.0)
            update_timing["update_calls"] += 1
            update_call_seconds.append(elapsed)

    model.train = _timed_train

    cpu_seconds_before = _process_tree_cpu_seconds()
    allocation_cgroup_before = _allocation_cgroup_metrics()
    started = time.monotonic()
    process_sampler = _ProcessTreeSampler(os.getpid()) if profile_phases else None
    gpu_sampler = (
        _NvidiaSmiSampler(phase_provider=process_sampler.current_phase)
        if profile_phases and device == "cuda" and process_sampler is not None
        else None
    )
    if gpu_sampler is not None:
        gpu_sampler.start()
    if process_sampler is not None:
        process_sampler.start()
    gpu_telemetry: dict[str, Any] | None = None
    process_tree_telemetry: dict[str, Any] | None = None
    with ExitStack() as profile_stack:
        profile_stack.enter_context(
            _time_method_calls(
                model,
                "collect_rollouts",
                rollout_call_seconds,
                profile=profile_phases,
                range_name="ppo.collect_rollouts",
                cpu_samples=phase_cpu_seconds["collect_rollouts"],
                cuda_event_pairs=phase_cuda_event_pairs["collect_rollouts"],
                process_sampler=process_sampler,
            )
        )
        if profile_phases:
            import learning.rl.environment_adapter as environment_adapter_module

            profile_stack.enter_context(
                _time_method_calls(
                    model.policy,
                    "forward",
                    method_wall_seconds["policy_forward"],
                    profile=True,
                    range_name="ppo.policy_forward",
                    process_sampler=process_sampler,
                )
            )
            profile_stack.enter_context(
                _time_method_calls(
                    model.policy,
                    "evaluate_actions",
                    method_wall_seconds["policy_evaluate_actions"],
                    profile=True,
                    range_name="ppo.evaluate_actions",
                    process_sampler=process_sampler,
                )
            )
            profile_stack.enter_context(
                _time_callable(
                    environment_adapter_module,
                    "_stack_observations",
                    method_wall_seconds["parent_observation_stack"],
                    range_name="env.parent_observation_stack",
                    process_sampler=process_sampler,
                )
            )
            profile_stack.enter_context(
                _time_method_calls(
                    model.rollout_buffer,
                    "add",
                    method_wall_seconds["rollout_buffer_add"],
                    profile=True,
                    range_name="ppo.rollout_buffer_add",
                    process_sampler=process_sampler,
                )
            )
            profile_stack.enter_context(
                _time_method_calls(
                    model.rollout_buffer,
                    "compute_returns_and_advantage",
                    method_wall_seconds["gae"],
                    profile=True,
                    range_name="ppo.gae",
                    process_sampler=process_sampler,
                )
            )
            if device == "cuda":
                profile_stack.enter_context(
                    _time_tensor_backward(
                        torch,
                        method_wall_seconds["backward"],
                        process_sampler,
                    )
                )
                profile_stack.enter_context(
                    _time_callable(
                        model.policy.optimizer,
                        "step",
                        method_wall_seconds["optimizer_step"],
                        range_name="ppo.optimizer_step",
                        process_sampler=process_sampler,
                    )
                )
                profile_stack.enter_context(
                    _time_callable(
                        torch.cuda,
                        "synchronize",
                        method_wall_seconds["cuda_synchronize"],
                        range_name="ppo.cuda_synchronize",
                        process_sampler=process_sampler,
                    )
                )
            for method_name, key in (
                ("step_async", "vec_step_async"),
                ("step_wait", "vec_step_wait"),
            ):
                if hasattr(vec_env, method_name):
                    profile_stack.enter_context(
                        _time_method_calls(
                            vec_env,
                            method_name,
                            method_wall_seconds[key],
                            profile=True,
                            range_name=f"ppo.{key}",
                            process_sampler=process_sampler,
                        )
                    )
        try:
            model.learn(total_timesteps=total_timesteps, progress_bar=False)
        finally:
            if gpu_sampler is not None:
                gpu_telemetry = gpu_sampler.stop()
            if process_sampler is not None:
                process_tree_telemetry = process_sampler.stop()
    if device == "cuda":
        sync_started = time.perf_counter()
        torch.cuda.synchronize()
        final_cuda_wait_seconds = time.perf_counter() - sync_started
        if profile_phases:
            method_wall_seconds["cuda_synchronize"].append(final_cuda_wait_seconds)
    else:
        final_cuda_wait_seconds = None
    training_seconds = time.monotonic() - started
    cpu_seconds_after = _process_tree_cpu_seconds()
    allocation_cgroup_after = _allocation_cgroup_metrics()
    model.train = original_train
    model.policy.optimizer.step = original_optimizer_step

    env_step_stats: list[_StepTiming] = []
    env_step_shard_seconds: list[float] = []
    env_observation_seconds = 0.0
    env_observation_calls = 0
    if measure_env_steps or profile_phases:
        env_step_stats = vec_env.env_method("get_step_timing")
        env_observation_seconds = sum(
            float(item["observation_construction_seconds"]) for item in env_step_stats
        )
        env_observation_calls = sum(
            int(item["observation_construction_calls"]) for item in env_step_stats
        )
        widths = getattr(vec_env, "logical_envs_per_shard", [1] * len(env_step_stats))
        cursor = 0
        for width in widths:
            env_step_shard_seconds.append(
                sum(float(item["seconds"]) for item in env_step_stats[cursor : cursor + width])
            )
            cursor += width

    # SB3 counts every per-env step into ``num_timesteps``, so this is the real
    # number of env steps the rollout produced (>= total_timesteps because the
    # last rollout overshoots).
    actual_env_steps = int(model.num_timesteps)
    update_seconds = float(update_timing["update_seconds"])
    rollout_wall_seconds_total = sum(rollout_call_seconds)
    unattributed_training_wall_seconds = max(
        training_seconds - rollout_wall_seconds_total - update_seconds, 0.0
    )
    rollout_and_framework_seconds = max(training_seconds - update_seconds, 0.0)
    completed_rollouts = len(rollout_call_seconds)
    measured_rollout_seconds = sum(rollout_call_seconds[warmup_rollouts:])
    measured_update_seconds = sum(update_call_seconds[warmup_rollouts:])
    measured_rollout_count = max(completed_rollouts - warmup_rollouts, 0)
    measured_env_steps = measured_rollout_count * nominal_env_steps
    measured_core_seconds = measured_rollout_seconds + measured_update_seconds
    measured_core_fps = measured_env_steps / max(measured_core_seconds, 1e-9)
    process_tree_cpu_seconds = max(cpu_seconds_after - cpu_seconds_before, 0.0)
    average_cpu_cores = process_tree_cpu_seconds / max(training_seconds, 1e-9)
    allocated_cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) or None
    head_cfg = cfg.agent.get("head_arch", {})

    gpu_after: dict[str, int] = {}
    if device == "cuda":
        torch.cuda.synchronize()
        free_bytes, _ = torch.cuda.mem_get_info()
        gpu_after = {
            "gpu_free_after_bytes": free_bytes,
            "gpu_allocated_bytes": torch.cuda.memory_allocated(),
            "gpu_reserved_bytes": torch.cuda.memory_reserved(),
            "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        }

    cuda_stream_elapsed_ms: dict[str, list[float]] = {}
    if device == "cuda":
        for phase_name, event_pairs in phase_cuda_event_pairs.items():
            cuda_stream_elapsed_ms[phase_name] = [
                float(start_event.elapsed_time(end_event)) for start_event, end_event in event_pairs
            ]
    sampled_env_step_ms = [
        elapsed_ms for item in env_step_stats for elapsed_ms in item.get("sampled_step_ms", [])
    ]
    sampled_decision_indices = [
        [int(index) for index in item.get("sampled_decision_indices", [])]
        for item in env_step_stats
    ]
    aligned_sample_count = min(map(len, sampled_decision_indices), default=0)
    unique_market_indices_per_vector_step = [
        len({indices[sample_idx] for indices in sampled_decision_indices})
        for sample_idx in range(aligned_sample_count)
    ]
    market_reuse_per_vector_step = [
        len(sampled_decision_indices) / unique_count
        for unique_count in unique_market_indices_per_vector_step
        if unique_count
    ]

    source_patch_identity = _working_tree_patch_identity(PROJECT_ROOT)
    report = {
        "profile_scope": "ppo_core_without_production_callbacks",
        "production_callbacks_included": False,
        "callback_evaluation_seconds": None,
        "checkpoint_seconds": None,
        "git_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "working_tree_dirty": source_patch_identity["working_tree_dirty"],
        "source_patch_identity": source_patch_identity,
        "source_patch_identity_sha256": source_patch_identity["patch_identity_sha256"],
        "benchmark_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "variant": variant,
        "config_path": str(config_path) if config_path is not None else None,
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "config_sha256": config_sha256,
        "resolved_config_yaml": cfg_text,
        "bundle_manifest_sha256": (
            hashlib.sha256((bundle_path / "manifest.json").read_bytes()).hexdigest()
            if (bundle_path / "manifest.json").is_file()
            else None
        ),
        "arch": arch,
        "algo": algo,
        "seed": seed,
        "n_envs": int(model.n_envs),
        "vector_backend": vector_backend,
        "rollout_buffer_class": type(model.rollout_buffer).__name__,
        "rollout_buffer_on_device": bool(cfg.ppo.get("rollout_buffer_on_device", False)),
        "defer_metric_sync": bool(cfg.ppo.get("defer_metric_sync", False)),
        "ppo_class": type(model).__name__,
        "policy_class": type(model.policy).__name__,
        "high_throughput_runtime_identity_validation": runtime_identity_validation,
        "torch_compile_mode": torch_compile_mode,
        "torch_compile_warmup_seconds": compile_warmup_seconds,
        "matmul_precision": torch.get_float32_matmul_precision(),
        "env_step_timing_enabled": measure_env_steps or profile_phases,
        "phase_profile_enabled": profile_phases,
        "gpu_telemetry": gpu_telemetry,
        "process_thread_telemetry": process_tree_telemetry,
        "allocation_cgroup_before": allocation_cgroup_before,
        "allocation_cgroup_after": allocation_cgroup_after,
        "phase_profile_note": (
            "NVTX/CUDA event ranges annotate PPO phases; CUDA event elapsed time includes "
            "stream gaps and is not SM-active time. CPU method timings are diagnostic and "
            "profiled runs are not comparable to unprofiled FPS baselines."
            if profile_phases
            else None
        ),
        "phase_cpu_process_seconds": {
            key: _sample_summary(values) for key, values in phase_cpu_seconds.items()
        },
        "final_cuda_wait_seconds": final_cuda_wait_seconds,
        "phase_cuda_stream_elapsed_ms": {
            key: _sample_summary(values) for key, values in cuda_stream_elapsed_ms.items()
        },
        "method_wall_ms": {
            key: _sample_summary(values, scale=1000.0)
            for key, values in method_wall_seconds.items()
        },
        "env_step_calls": sum(int(item["steps"]) for item in env_step_stats),
        "env_step_cpu_seconds_total": sum(float(item["seconds"]) for item in env_step_stats),
        "env_observation_construction_seconds": env_observation_seconds,
        "env_observation_construction_calls": env_observation_calls,
        "env_step_sampled_latency_ms": _sample_summary(sampled_env_step_ms),
        "sampled_unique_decision_indices_per_vector_step": _sample_summary(
            [float(value) for value in unique_market_indices_per_vector_step]
        ),
        "sampled_market_reuse_factor_per_vector_step": _sample_summary(
            market_reuse_per_vector_step
        ),
        "decision_index_sample_interval_env_steps": 8,
        "decision_index_sample_count": aligned_sample_count,
        "decision_index_profile_available": aligned_sample_count > 0,
        "env_step_wall_lower_bound_seconds": max(env_step_shard_seconds, default=0.0),
        "env_step_mean_ms": (
            1000.0
            * sum(float(item["seconds"]) for item in env_step_stats)
            / max(sum(int(item["steps"]) for item in env_step_stats), 1)
        ),
        "env_step_shard_seconds": env_step_shard_seconds,
        "configured_vector_backend": str(cfg.env.get("vector_backend", "subproc")),
        "physical_worker_count": physical_worker_count,
        "logical_envs_per_worker": logical_envs_per_worker
        if logical_envs_per_worker is not None
        else [1] * physical_worker_count,
        "total_timesteps": total_timesteps,
        "warmup_rollouts_excluded_from_core_rate": warmup_rollouts,
        "completed_rollouts": completed_rollouts,
        "rollout_call_seconds": rollout_call_seconds,
        "update_call_seconds": update_call_seconds,
        "measured_rollout_count": measured_rollout_count,
        "measured_env_steps_after_warmup": measured_env_steps,
        "measured_rollout_seconds_after_warmup": measured_rollout_seconds,
        "measured_update_seconds_after_warmup": measured_update_seconds,
        "measured_ppo_core_seconds_after_warmup": measured_core_seconds,
        "measured_ppo_core_steps_per_second": measured_core_fps,
        "rollout_steps_per_env": rollout_steps_per_env,
        "aggregate_rollout_size": nominal_env_steps,
        "n_epochs": int(model.n_epochs),
        "batch_size": int(model.batch_size),
        "minibatches_per_epoch": int(
            (nominal_env_steps + int(model.batch_size) - 1) // int(model.batch_size)
        ),
        "optimizer_steps": optimizer_timing["optimizer_steps"],
        "ppo_epochs_completed": int(getattr(model, "_n_updates", 0)),
        "configured_ppo_n_steps": int(cfg.ppo.n_steps),
        "effective_ppo_n_steps_per_env": int(model.n_steps),
        "learning_rate": float(cfg.ppo.learning_rate),
        "gamma": float(cfg.ppo.gamma),
        "gae_lambda": float(cfg.ppo.gae_lambda),
        "clip_range": float(cfg.ppo.clip_range),
        "ent_coef": float(cfg.ppo.ent_coef),
        "effective_ent_coef": float(model.ent_coef),
        "parameter_count": sum(p.numel() for p in model.policy.parameters()),
        "feature_extractor_class": type(model.policy.features_extractor).__name__,
        "encoder_spec": {
            "channels": getattr(model.policy.features_extractor, "channels", None),
            "dilations": list(model.policy.features_extractor.dilations)
            if hasattr(model.policy.features_extractor, "dilations")
            else None,
            "kernel_size": getattr(model.policy.features_extractor, "kernel_size", None),
            "latent_dim": int(getattr(model.policy.features_extractor, "latent_dim", 128)),
            "parameters": {
                key: getattr(model.policy.features_extractor, key)
                for key in ("hidden_size", "num_layers", "d_model", "nhead", "dim_feedforward")
                if hasattr(model.policy.features_extractor, key)
            },
            "receptive_field": getattr(model.policy.features_extractor, "receptive_field", None),
        },
        "policy_head_architecture": [int(width) for width in head_cfg.get(arch, [256, 128])],
        "observation_shapes": {
            key: list(space.shape or ())
            for key, space in parent_env.observation_space.spaces.items()
        },
        "action_space": {
            "class": type(parent_env.action_space).__name__,
            "shape": list(getattr(parent_env.action_space, "shape", ()) or ()),
            "n": getattr(parent_env.action_space, "n", None),
        },
        "action_schema": (
            parent_env.action_schema.to_dict()
            if hasattr(parent_env, "action_schema") and hasattr(parent_env.action_schema, "to_dict")
            else None
        ),
        "device": device,
        "bundle_size_bytes": sum(
            path.stat().st_size for path in bundle_path.iterdir() if path.is_file()
        ),
        "cgroup_start_bytes": start_bytes,
        "cgroup_vecenv_ready_bytes": vecenv_bytes,
        "cgroup_after_training_bytes": _cgroup_memory_bytes(),
        "trainer_tree_pss_mib": _tree_pss_mib(os.getpid()),
        "process_tree_cpu_seconds": process_tree_cpu_seconds,
        "average_cpu_cores_used": average_cpu_cores,
        "allocated_cpus": allocated_cpus,
        "allocated_cpu_fraction": (
            average_cpu_cores / allocated_cpus if allocated_cpus is not None else None
        ),
        "training_seconds": training_seconds,
        "total_wallclock_seconds": training_seconds,
        "rollout_wall_seconds_total": rollout_wall_seconds_total,
        "unattributed_training_wall_seconds": unattributed_training_wall_seconds,
        "env_steps_per_second": actual_env_steps / max(training_seconds, 1e-9),
        "effective_total_timesteps": total_timesteps,
        "actual_env_steps": actual_env_steps,
        "nominal_env_steps_per_rollout_window": nominal_env_steps,
        "update_seconds": update_seconds,
        "update_compute_seconds": float(update_timing["update_compute_seconds"]),
        "update_semaphore_wait_seconds": float(update_timing["update_semaphore_wait_seconds"]),
        "update_semaphore_slots": update_semaphore_slots or None,
        "update_calls": update_timing["update_calls"],
        "rollout_and_framework_overhead_seconds": rollout_and_framework_seconds,
        "rollout_steps_per_second": actual_env_steps / max(rollout_and_framework_seconds, 1e-9),
        "update_share_of_wallclock": update_seconds / max(training_seconds, 1e-9),
        **gpu_before,
        **gpu_after,
    }
    model.get_env().close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=_json_default) + "\n")
    return report


def main() -> None:
    args = _parse_args()
    if (
        (args.n_envs is not None and args.n_envs < 1)
        or (args.rollout_steps_per_env is not None and args.rollout_steps_per_env < 1)
        or (args.batch_size is not None and args.batch_size < 1)
        or (args.total_timesteps is not None and args.total_timesteps < 1)
        or args.warmup_rollouts < 0
        or args.update_semaphore_slots < 0
    ):
        raise SystemExit(
            "n_envs, rollout steps, batch size, and total_timesteps must be positive; "
            "warmup rollouts and update semaphore slots cannot be negative"
        )
    if (args.update_semaphore_slots > 0) != (args.update_semaphore_dir is not None):
        raise SystemExit(
            "set both --update-semaphore-slots and --update-semaphore-dir for semaphore probes"
        )
    report = _train_probe(
        args.n_envs,
        args.rollout_steps_per_env,
        args.total_timesteps,
        args.device,
        args.output,
        args.bundle_dir,
        args.variant,
        args.config,
        args.overrides,
        args.seed,
        args.batch_size,
        args.torch_compile_mode,
        args.matmul_precision,
        args.measure_env_steps,
        args.update_semaphore_dir,
        args.update_semaphore_slots,
        args.warmup_rollouts,
        args.profile_phases,
    )
    print(json.dumps(report, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
