from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from compute.slurm import resources as sample_experiment_run_resources
from compute.slurm.resources import allocation_cgroup_file, cgroup_file


def test_cgroup_file_follows_nested_v2_process_cgroup(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "fs" / "cgroup"
    nested = root / "slurm" / "uid_1" / "job_2" / "step_0"
    nested.mkdir(parents=True)
    (nested / "memory.current").write_text("1234\n")
    proc = tmp_path / "proc" / "self" / "cgroup"
    proc.parent.mkdir(parents=True)
    proc.write_text("0::/slurm/uid_1/job_2/step_0\n")

    assert cgroup_file("memory.current", proc_cgroup=proc, cgroup_root=root) == (
        nested / "memory.current"
    )


def test_allocation_cgroup_file_uses_slurm_job_parent(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "fs" / "cgroup"
    job = root / "slurm" / "uid_1" / "job_2"
    step = job / "step_3" / "task_0"
    step.mkdir(parents=True)
    (job / "memory.current").write_text("9000\n")
    (step / "memory.current").write_text("1000\n")
    proc = tmp_path / "proc" / "worker" / "cgroup"
    proc.parent.mkdir(parents=True)
    proc.write_text("0::/slurm/uid_1/job_2/step_3/task_0\n")

    assert cgroup_file("memory.current", proc_cgroup=proc, cgroup_root=root) == (
        step / "memory.current"
    )
    assert allocation_cgroup_file("memory.current", proc_cgroup=proc, cgroup_root=root) == (
        job / "memory.current"
    )


def test_cgroup_file_follows_v1_memory_controller(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "fs" / "cgroup"
    nested = root / "memory" / "slurm" / "job_2"
    nested.mkdir(parents=True)
    (nested / "memory.usage_in_bytes").write_text("5678\n")
    proc = tmp_path / "proc" / "self" / "cgroup"
    proc.parent.mkdir(parents=True)
    proc.write_text("5:cpu,memory:/slurm/job_2\n")

    assert (
        cgroup_file("memory.usage_in_bytes", proc_cgroup=proc, cgroup_root=root)
        == nested / "memory.usage_in_bytes"
    )


def test_cgroup_file_rejects_paths_escaping_mount(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "fs" / "cgroup"
    root.mkdir(parents=True)
    outside = tmp_path / "secret"
    outside.write_text("not a cgroup value")
    proc = tmp_path / "proc" / "self" / "cgroup"
    proc.parent.mkdir(parents=True)
    proc.write_text("0::/../../secret\n")

    assert cgroup_file("secret", proc_cgroup=proc, cgroup_root=root) is None


def test_process_stat_cpu_usec_parses_user_and_system_time() -> None:
    fields = ["S"] + ["0"] * 12
    fields[11] = "125"
    fields[12] = "75"
    stat = f"123 (worker process) {' '.join(fields)}"

    assert sample_experiment_run_resources._process_stat_cpu_usec(stat, 100) == 2_000_000


def test_process_stat_cpu_usec_handles_closing_parenthesis_in_process_name() -> None:
    fields = ["S"] + ["0"] * 12
    fields[11] = "125"
    fields[12] = "75"
    stat = f"123 (worker ) with spaces) {' '.join(fields)}"

    assert sample_experiment_run_resources._process_stat_cpu_usec(stat, 100) == 2_000_000


def test_process_stat_cpu_usec_returns_zero_for_truncated_record() -> None:
    assert sample_experiment_run_resources._process_stat_cpu_usec("123 (worker) S 0 0", 100) == 0


def test_read_process_table_ignores_non_process_entries_and_inaccessible_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proc = tmp_path / "proc"
    valid = proc / "101"
    inaccessible = proc / "102"
    valid.mkdir(parents=True)
    inaccessible.mkdir()
    (valid / "status").write_text("Name:\tworker\nPPid:\t50\n")
    entries = [valid, inaccessible, proc / "self"]
    original_read = Path.read_text

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == inaccessible / "status":
            raise PermissionError("denied")
        return original_read(path, *args, **kwargs)

    original_iterdir = Path.iterdir

    def iterdir(path: Path):
        return iter(entries) if path == Path("/proc") else original_iterdir(path)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "iterdir", iterdir)

    assert sample_experiment_run_resources.read_process_table() == {101: 50}


def test_descendants_and_process_memory_skip_unreadable_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert sample_experiment_run_resources.descendant_pids([10], {11: 10, 12: 11, 13: 99}) == {
        10,
        11,
        12,
    }
    original_read = Path.read_text
    values = {
        "/proc/10/smaps_rollup": "Rss: 10 kB\nPss: 4 kB\n",
        "/proc/11/smaps_rollup": "Rss: 10 kB\n",
    }

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if str(path) in values:
            return values[str(path)]
        if str(path).startswith("/proc/"):
            raise FileNotFoundError(str(path))
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    assert sample_experiment_run_resources.pss_bytes({10, 11, 12}) == 4096


def test_process_io_and_cpu_counters_ignore_missing_or_malformed_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = Path.read_text
    contents = {
        "/proc/10/io": "rchar: 1\nwchar: 2\nread_bytes: 3\nwrite_bytes: 4\nmalformed\n",
        "/proc/10/stat": "10 (worker process) S 0 0 0 0 0 0 0 0 0 0 125 75 0 0 0",
        "/proc/11/io": "rchar: 10\nunknown: 9\nwchar: 20\nread_bytes: 30\nwrite_bytes: 40\n",
        "/proc/11/stat": "invalid stat fields",
    }

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if str(path) in contents:
            return contents[str(path)]
        if str(path).startswith("/proc/"):
            raise FileNotFoundError(str(path))
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr("compute.slurm.resources.os.sysconf", lambda _name: 100)

    assert sample_experiment_run_resources.process_io_bytes({10, 11, 12}) == (11, 22, 33, 44)
    assert sample_experiment_run_resources.process_tree_cpu_usec({10, 11, 12}) == 2_000_000


@pytest.mark.parametrize(
    "returncode,stdout,expected", [(0, "85, 100\ninvalid\n", ([85], [100])), (1, "", ([], []))]
)
def test_gpu_sample_parses_valid_rows_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: str,
    expected: tuple[list[int], list[int]],
) -> None:
    monkeypatch.setattr(
        "compute.slurm.resources.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=returncode, stdout=stdout),
    )

    assert sample_experiment_run_resources.gpu_sample() == expected


def test_gpu_sample_handles_missing_command(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr("compute.slurm.resources.subprocess.run", unavailable)
    assert sample_experiment_run_resources.gpu_sample() == ([], [])


def test_gpu_sample_preserves_each_device(monkeypatch) -> None:
    monkeypatch.setattr(
        "compute.slurm.resources.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="86, 44167\n81, 43583\n"),
    )

    assert sample_experiment_run_resources.gpu_sample() == ([86, 81], [44167, 43583])


def test_active_roots_selects_remote_workers_for_this_node(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("compute.slurm.resources.socket.gethostname", lambda: "gpuarm2.int")
    first = tmp_path / "gpuarm1.json"
    second = tmp_path / "gpuarm2.json"
    first.write_text(json.dumps({"hostname": "gpuarm1", "pid": 101}))
    second.write_text(json.dumps({"hostname": "gpuarm2", "pid": 202}))
    experiment_run = tmp_path / "experiment_run.json"
    experiment_run.write_text(
        json.dumps(
            {
                "jobs": [
                    {"status": "running", "remote_pid_file": str(first)},
                    {"status": "running", "remote_pid_file": str(second)},
                    {"status": "pending"},
                ]
            }
        )
    )

    roots, active = sample_experiment_run_resources.active_roots(experiment_run)

    assert roots == [202]
    assert active is True


def test_active_roots_respects_stopping_pending_and_local_worker_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("compute.slurm.resources.socket.gethostname", lambda: "gpu1.domain")
    stopped = tmp_path / "stopped.json"
    stopped.write_text(json.dumps({"stopping": True, "jobs": [{"status": "running", "pid": 11}]}))
    assert sample_experiment_run_resources.active_roots(stopped) == ([], False)

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json")
    assert sample_experiment_run_resources.active_roots(invalid) == ([], False)

    remote = tmp_path / "remote.json"
    remote.write_text("not-json")
    local = tmp_path / "local.json"
    local.write_text(json.dumps({"hostname": "gpu1", "pid": 22}))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "jobs": [
                    {"status": "pending", "pid": 1},
                    {"status": "running", "worker_node": "gpu2", "pid": 2},
                    {"status": "running", "worker_node": "gpu1", "pid": "23"},
                    {"status": "running", "remote_pid_file": str(remote)},
                    {"status": "running", "remote_pid_file": str(local)},
                ]
            }
        )
    )

    assert sample_experiment_run_resources.active_roots(manifest) == ([23, 22], True)


def test_cgroup_scope_distinguishes_job_scope_and_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sample_experiment_run_resources,
        "cgroup_file",
        lambda _name: Path("/cgroup/step/memory.current"),
    )
    monkeypatch.setattr(
        sample_experiment_run_resources,
        "allocation_cgroup_file",
        lambda _name: Path("/cgroup/job/memory.current"),
    )
    assert sample_experiment_run_resources.cgroup_memory_scope() == "slurm_job"

    monkeypatch.setattr(sample_experiment_run_resources, "cgroup_file", lambda _name: None)
    assert sample_experiment_run_resources.cgroup_memory_scope() == "unavailable"


def test_sampler_csv_records_cpu_time_and_memory_scope(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "resources.csv"
    experiment_run = tmp_path / "experiment_run.json"
    experiment_run.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sample_experiment_run_resources.py",
            "--experiment-run",
            str(experiment_run),
            "--out",
            str(output),
        ],
    )
    monkeypatch.setattr(sample_experiment_run_resources, "active_roots", lambda _path: ([], False))
    monkeypatch.setattr(sample_experiment_run_resources, "read_process_table", lambda: {})
    monkeypatch.setattr(
        sample_experiment_run_resources, "process_io_bytes", lambda _pids: (1, 2, 3, 4)
    )
    monkeypatch.setattr(sample_experiment_run_resources, "gpu_sample", lambda: ([75], [1234]))
    monkeypatch.setattr("compute.slurm.resources.os.getloadavg", lambda: (1.0, 0.5, 0.2))
    monkeypatch.setattr(sample_experiment_run_resources, "pss_bytes", lambda _pids: 5678)
    monkeypatch.setattr(
        sample_experiment_run_resources,
        "cgroup_value",
        lambda name: {
            "memory.current": "100",
            "memory.max": "200",
            "memory.peak": "150",
            "memory.events": "low 0",
        }.get(name, ""),
    )
    monkeypatch.setattr(
        sample_experiment_run_resources, "process_tree_cpu_usec", lambda _pids: 9_000_000
    )
    monkeypatch.setattr(sample_experiment_run_resources, "cgroup_memory_scope", lambda: "slurm_job")

    assert sample_experiment_run_resources.main() == 0

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["process_tree_cpu_time_usec"] == "9000000"
    assert rows[0]["cgroup_memory_scope"] == "slurm_job"
    assert rows[0]["cgroup_memory_peak"] == "150"


def test_sampler_emits_periodic_samples_until_workers_finish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing.csv"
    output.write_text("existing-header\n")
    experiment_run = tmp_path / "manifest.json"
    experiment_run.write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sampler",
            "--experiment-run",
            str(experiment_run),
            "--out",
            str(output),
            "--interval",
            "0.5",
        ],
    )
    active_states = iter([([10], True), ([], False)])
    monkeypatch.setattr(
        sample_experiment_run_resources,
        "active_roots",
        lambda _path: next(active_states),
    )
    samples: list[str] = []
    monkeypatch.setattr(
        sample_experiment_run_resources, "sample", lambda *_args: samples.append("sample")
    )
    sleep = Mock()
    monkeypatch.setattr("compute.slurm.resources.time.sleep", sleep)

    assert sample_experiment_run_resources.main() == 0

    assert samples == ["sample", "sample"]
    sleep.assert_called_once_with(0.5)
    assert output.read_text() == "existing-header\n"
