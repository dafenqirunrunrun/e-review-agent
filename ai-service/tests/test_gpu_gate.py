import os
import sys
import tempfile
from pathlib import Path

import pytest

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.runtime import gpu_gate
from app.runtime.gpu_gate import GpuDriverMode, GpuProcess, GpuStatus, evaluate_busy, evaluate_gate, wait_for_gpu_idle


def idle_status():
    return GpuStatus(
        ok=True,
        gpu_name="NVIDIA GeForce RTX 4060 Laptop GPU",
        gpu_uuid="GPU-test",
        utilization_percent=0,
        memory_used_mb=512,
        memory_free_mb=7600,
        memory_total_mb=8192,
        driver_mode=GpuDriverMode.WDDM,
        foreign_processes=[],
    )


def test_idle_requires_stable_checks():
    calls = []

    def status_fn():
        calls.append(1)
        return idle_status()

    result = wait_for_gpu_idle(
        stage="test",
        stable_checks=3,
        check_interval_seconds=0,
        timeout_seconds=1,
        status_fn=status_fn,
        sleep_fn=lambda _: None,
    )
    assert result.gpu_name
    assert len(calls) == 3


def test_foreign_process_is_busy():
    status = idle_status()
    status.foreign_processes = [GpuProcess(pid=1234, process_name="python.exe", used_gpu_memory_mb=4096)]
    busy, reasons = evaluate_busy(status, min_free_memory_mb=6000)
    assert busy
    assert "FOREIGN_COMPUTE_PROCESS" in reasons


def test_high_utilization_is_busy():
    status = idle_status()
    status.utilization_percent = 83
    busy, reasons = evaluate_busy(status)
    assert busy
    assert "GPU_UTILIZATION_BUSY" in reasons


def test_wddm_35_percent_graphics_activity_passes_when_compute_and_memory_clear():
    status = idle_status()
    status.utilization_percent = 35
    status.memory_free_mb = 6280
    status.wddm_graphics_process_count = 16
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="wddm-aware", memory_free_samples=[6280, 6280, 6280])
    assert decision.allowed is True
    assert decision.decision == "allowed"
    assert "GPU_WDDM_GRAPHICS_ACTIVITY_TOLERATED" in decision.reason_codes


def test_wddm_59_percent_graphics_activity_passes():
    status = idle_status()
    status.utilization_percent = 59
    status.memory_free_mb = 6280
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="wddm-aware", memory_free_samples=[6300, 6290, 6280])
    assert decision.allowed is True


def test_wddm_61_percent_utilization_blocks():
    status = idle_status()
    status.utilization_percent = 61
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="wddm-aware", memory_free_samples=[6280, 6280, 6280])
    assert decision.allowed is False
    assert decision.decision == "blocked_high_utilization"
    assert "GPU_UTILIZATION_EXTREME" in decision.reason_codes


def test_low_free_memory_is_busy():
    status = idle_status()
    status.memory_free_mb = 1024
    busy, reasons = evaluate_busy(status)
    assert busy
    assert "GPU_MEMORY_BUSY" in reasons


def test_wddm_low_free_memory_blocks():
    status = idle_status()
    status.memory_free_mb = 5199
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="wddm-aware", memory_free_samples=[5199, 5199, 5199])
    assert decision.allowed is False
    assert decision.decision == "blocked_memory"


def test_wddm_declining_free_memory_blocks():
    status = idle_status()
    status.memory_free_mb = 6000
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="wddm-aware", memory_free_samples=[6400, 6250, 6000])
    assert decision.allowed is False
    assert decision.decision == "blocked_memory"
    assert "GPU_MEMORY_DECLINING" in decision.reason_codes


def test_wddm_numeric_compute_process_blocks():
    status = idle_status()
    status.foreign_processes = [GpuProcess(pid=2222, process_name="python.exe", used_gpu_memory_mb=1024)]
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="wddm-aware")
    assert decision.allowed is False
    assert decision.decision == "blocked_compute_process"


def test_timeout_when_never_idle():
    status = idle_status()
    status.utilization_percent = 99
    with pytest.raises(TimeoutError):
        wait_for_gpu_idle(
            stage="test",
            stable_checks=1,
            check_interval_seconds=0,
            timeout_seconds=1,
            status_fn=lambda: status,
            sleep_fn=lambda _: None,
        )


def test_stale_lock_cleanup(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "e-review-gpu.lock"
        path.write_text('{"pid": 99999999, "stage": "old"}', encoding="utf-8")
        monkeypatch.setattr(gpu_gate, "is_pid_alive", lambda pid: False)
        assert gpu_gate.clear_stale_lock(path) is True
        assert not path.exists()


def test_valid_lock_blocks(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "e-review-gpu.lock"
        path.write_text('{"pid": 111, "stage": "other"}', encoding="utf-8")
        monkeypatch.setattr(gpu_gate, "LOCK_PATH", path)
        monkeypatch.setattr(gpu_gate, "is_pid_alive", lambda pid: True)
        busy, reasons = evaluate_busy(idle_status())
        assert busy
    assert "GPU_LOCK_BLOCKED" in reasons


def test_wddm_valid_external_lock_blocks(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "e-review-gpu.lock"
        path.write_text('{"pid": 111, "stage": "other"}', encoding="utf-8")
        monkeypatch.setattr(gpu_gate, "LOCK_PATH", path)
        monkeypatch.setattr(gpu_gate, "is_pid_alive", lambda pid: True)
        decision = evaluate_gate(idle_status(), min_free_memory_mb=5200, gpu_gate_mode="wddm-aware")
        assert decision.allowed is False
        assert decision.decision == "blocked_lock"
        assert "GPU_EXTERNAL_LOCK_PRESENT" in decision.reason_codes


def test_self_pid_process_not_foreign(monkeypatch):
    class Result:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    current = os.getpid()

    def runner(args):
        if "--query-gpu=index,uuid,name,utilization.gpu,memory.used,memory.free,memory.total" in args:
            return Result("0, GPU-test, NVIDIA GeForce RTX 4060 Laptop GPU, 0, 512, 7600, 8192\n")
        return Result(f"{current}, python.exe, 256, GPU-test\n")

    status = gpu_gate.query_gpu_status(current_pid=current, runner=runner)
    assert status.foreign_process_count == 0


def test_wddm_na_memory_processes_do_not_block_when_free_memory_is_stable():
    status = idle_status()
    status.memory_used_mb = 2423
    status.memory_free_mb = 5535
    status.wddm_graphics_process_count = 30
    status.foreign_processes = []
    busy, reasons = evaluate_busy(status, min_free_memory_mb=5200)
    assert busy is False
    assert reasons == []


def test_tcc_auto_keeps_strict_utilization_policy():
    status = idle_status()
    status.driver_mode = GpuDriverMode.TCC
    status.utilization_percent = 35
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="auto")
    assert decision.allowed is False
    assert decision.policy_mode.value == "strict"
    assert decision.decision == "blocked_high_utilization"


def test_unknown_driver_mode_does_not_become_wddm_aware():
    status = idle_status()
    status.driver_mode = GpuDriverMode.UNKNOWN
    status.utilization_percent = 35
    decision = evaluate_gate(status, min_free_memory_mb=5200, gpu_gate_mode="auto")
    assert decision.allowed is False
    assert decision.policy_mode.value == "strict"


def test_wddm_wait_for_gpu_idle_tolerates_graphics_activity():
    status = idle_status()
    status.utilization_percent = 35
    status.memory_free_mb = 6280
    calls = []

    def status_fn():
        calls.append(1)
        return status

    result = wait_for_gpu_idle(
        stage="wddm-test",
        min_free_memory_mb=5200,
        stable_checks=3,
        check_interval_seconds=0,
        timeout_seconds=1,
        gpu_gate_mode="wddm-aware",
        status_fn=status_fn,
        sleep_fn=lambda _: None,
    )
    assert result.gpu_name
    assert len(calls) == 3


def test_numeric_gpu_memory_process_is_real_compute():
    status = idle_status()
    status.foreign_processes = [GpuProcess(pid=2222, process_name="python.exe", used_gpu_memory_mb=1024)]
    busy, reasons = evaluate_busy(status, min_free_memory_mb=5200)
    assert busy is True
    assert "FOREIGN_COMPUTE_PROCESS" in reasons
