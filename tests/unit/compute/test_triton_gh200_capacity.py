from __future__ import annotations

import importlib.util
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = Path(__file__).resolve().parents[3] / "compute/slurm/capacity.py"
SPEC = importlib.util.spec_from_file_location("check_gh200_capacity", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
capacity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capacity)


def _node(
    *, state: str = "MIXED", cpu_alloc: int = 48, memory_alloc: int = 524288, gpu_alloc: int = 1
) -> str:
    return (
        f"NodeName=gpuarm1 State={state} CPUAlloc={cpu_alloc} CPUTot=144 "
        f"RealMemory=1100000 AllocMem={memory_alloc} FreeMem=1100000 "
        "CfgTRES=cpu=144,mem=1100000M,gres/gpu=2,gres/gpu:gh200=2 "
        f"AllocTRES=cpu={cpu_alloc},mem={memory_alloc}M,gres/gpu={gpu_alloc},"
        f"gres/gpu:gh200={gpu_alloc}"
    )


def test_node_capacity_accepts_one_free_gh200_with_requested_cpu_and_ram() -> None:
    assert capacity.node_has_capacity(_node(), gpu_type="gh200", gpus=1, cpus=48, memory_mb=524288)


def test_node_capacity_accepts_mixed_node_with_one_gpu_already_allocated() -> None:
    assert capacity.node_has_capacity(
        _node(state="MIXED", cpu_alloc=8, memory_alloc=32768, gpu_alloc=1),
        gpu_type="gh200",
        gpus=1,
        cpus=48,
        memory_mb=524288,
    )


def test_node_capacity_rejects_busy_gpu_or_insufficient_cpu_or_ram() -> None:
    for output in (
        _node(gpu_alloc=2),
        _node(cpu_alloc=100),
        _node(memory_alloc=700000),
        _node().replace("FreeMem=1100000", "FreeMem=128000"),
        _node(state="DRAIN"),
    ):
        assert not capacity.node_has_capacity(
            output, gpu_type="gh200", gpus=1, cpus=48, memory_mb=524288
        )


@pytest.mark.parametrize(
    "state",
    ["DOWN", "DRAIN", "DRAINING", "FAIL", "NO_RESP", "FUTURE", "POWERED_DOWN", "MIXED+DRAIN"],
)
def test_node_capacity_rejects_unavailable_state_flags(state: str) -> None:
    assert not capacity.node_has_capacity(
        _node(state=state), gpu_type="gh200", gpus=1, cpus=1, memory_mb=1
    )


def test_node_capacity_rejects_missing_or_malformed_resource_fields() -> None:
    assert not capacity.node_has_capacity(
        "CPUAlloc=0 CPUTot=4 RealMemory=8 AllocMem=0 FreeMem=8 CfgTRES=gres/gpu:gh200=1",
        gpu_type="gh200",
        gpus=1,
        cpus=1,
        memory_mb=1,
    )
    assert not capacity.node_has_capacity(
        _node().replace("CPUTot=144", "CPUTot=unknown"),
        gpu_type="gh200",
        gpus=1,
        cpus=1,
        memory_mb=1,
    )


def test_node_capacity_requires_the_requested_gpu_tres_type() -> None:
    assert not capacity.node_has_capacity(_node(), gpu_type="h100", gpus=1, cpus=1, memory_mb=1)


def test_available_nodes_preserves_order_and_deduplicates_sinfo_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    details = {
        "gpuarm1": _node(gpu_alloc=1),
        "gpuarm2": _node(gpu_alloc=2),
        "gpuarm3": _node(gpu_alloc=0),
    }
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        if args[0] == "sinfo":
            return subprocess.CompletedProcess(
                args, 0, stdout="gpuarm1\ngpuarm1\ngpuarm2\ngpuarm3\n", stderr=""
            )
        return subprocess.CompletedProcess(args, 0, stdout=details[args[-1]], stderr="")

    monkeypatch.setattr(capacity.subprocess, "run", fake_run)
    available = capacity.available_nodes(
        "gpu-grace-h200-141g",
        gpu_type="gh200",
        gpus_per_node=1,
        cpus_per_node=48,
        memory_mb=524288,
    )

    assert available == ["gpuarm1", "gpuarm3"]
    assert [call[0][-1] for call in calls[1:]] == ["gpuarm1", "gpuarm2", "gpuarm3"]
    assert all(call[1]["check"] is True and call[1]["timeout"] == 15 for call in calls)


def test_available_nodes_propagates_a_failed_sinfo_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, args, stderr="partition unavailable")

    monkeypatch.setattr(capacity.subprocess, "run", fail_run)
    with pytest.raises(subprocess.CalledProcessError) as error:
        capacity.available_nodes(
            "missing-partition",
            gpu_type="gh200",
            gpus_per_node=1,
            cpus_per_node=1,
            memory_mb=1,
        )
    assert error.value.stderr == "partition unavailable"


def test_main_reports_available_nodes_and_respects_requested_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        capacity,
        "available_nodes",
        lambda *args, **kwargs: ["gpuarm1", "gpuarm2"],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["capacity", "--partition", "gpu", "--nodes", "1", "--gpu-type", "gh200"],
    )

    assert capacity.main() == 0
    assert capsys.readouterr().out == "available: gpuarm1\n"


def test_main_waits_when_too_few_nodes_meet_the_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(capacity, "available_nodes", lambda *args, **kwargs: ["gpuarm1"])
    monkeypatch.setattr(sys, "argv", ["capacity", "--partition", "gpu", "--nodes", "2"])

    assert capacity.main() == 1
    assert capsys.readouterr().out.startswith("waiting: 1/2 nodes have gh200 GPU")


def test_main_inspects_a_single_node_and_reports_capacity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=_node(), stderr="")

    monkeypatch.setattr(capacity.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capacity",
            "--partition",
            "gpu",
            "--node",
            "gpuarm1",
            "--nodes",
            "1",
            "--cpus-per-node",
            "48",
        ],
    )

    assert capacity.main() == 0
    assert calls == [["scontrol", "show", "node", "gpuarm1"]]
    assert capsys.readouterr().out == "available: gpuarm1\n"


def test_main_reports_slurm_query_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise OSError("scontrol is unavailable")

    monkeypatch.setattr(capacity.subprocess, "run", fail_run)
    monkeypatch.setattr(sys, "argv", ["capacity", "--partition", "gpu", "--node", "gpuarm1"])

    assert capacity.main() == 2
    assert capsys.readouterr().err == "Slurm capacity query failed: scontrol is unavailable\n"


def test_script_entrypoint_exits_with_main_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=_node(), stderr="")

    monkeypatch.setattr(capacity.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["capacity.py", "--partition", "gpu", "--node", "gpuarm1", "--nodes", "1"],
    )

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(MODULE_PATH), run_name="__main__")

    assert error.value.code == 0
