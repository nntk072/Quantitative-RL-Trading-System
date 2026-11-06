from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts/research/analysis/features/run_real_market_feature_prefix_audit.sh"
)


def _run_launcher(
    tmp_path: Path,
    *,
    slurm_job_id: str | None,
    hostname: str = "gpuarm1",
    gres: str = "gpu:gh200:1",
    cpus: str = "48",
    memory: str = "512G",
    time_limit: str = "12:00:00",
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    host_script = fake_bin / "hostname"
    host_script.write_text(f"#!/bin/sh\nprintf '%s\\n' '{hostname}'\n", encoding="utf-8")
    host_script.chmod(0o755)
    scontrol_script = fake_bin / "scontrol"
    scontrol_script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' 'JobId=123 Gres={gres} NumCPUs={cpus} "
        f"MinMemoryNode={memory} TimeLimit={time_limit}'\n",
        encoding="utf-8",
    )
    scontrol_script.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    if slurm_job_id is None:
        env.pop("SLURM_JOB_ID", None)
    else:
        env["SLURM_JOB_ID"] = slurm_job_id
    return subprocess.run(
        ["bash", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )


def test_launcher_rejects_missing_slurm_allocation(tmp_path: Path) -> None:
    result = _run_launcher(tmp_path, slurm_job_id=None)

    assert result.returncode == 2
    assert "existing Slurm allocation" in result.stderr


def test_launcher_rejects_non_gh200_node(tmp_path: Path) -> None:
    result = _run_launcher(tmp_path, slurm_job_id="123", hostname="login5")

    assert result.returncode == 2
    assert "Expected a GH200 node" in result.stderr


def test_launcher_rejects_allocations_with_more_than_one_gh200(tmp_path: Path) -> None:
    result = _run_launcher(tmp_path, slurm_job_id="123", gres="gpu:gh200:2")

    assert result.returncode == 2
    assert "Expected exactly one GH200" in result.stderr


def test_launcher_accepts_one_gh200_before_argument_validation(tmp_path: Path) -> None:
    result = _run_launcher(tmp_path, slurm_job_id="123")

    assert result.returncode == 2
    assert "Usage:" in result.stderr
    assert "Expected exactly one GH200" not in result.stderr


@pytest.mark.parametrize(
    ("resources", "expected_message"),
    [
        ({"cpus": "16"}, "at least 48 allocated CPUs"),
        ({"memory": "256G"}, "documented 512G host-memory allocation"),
        ({"time_limit": "06:00:00"}, "12-hour allocation"),
    ],
)
def test_launcher_rejects_insufficient_allocation_resources(
    tmp_path: Path,
    resources: dict[str, str],
    expected_message: str,
) -> None:
    result = _run_launcher(tmp_path, slurm_job_id="123", **resources)

    assert result.returncode == 2
    assert expected_message in result.stderr
