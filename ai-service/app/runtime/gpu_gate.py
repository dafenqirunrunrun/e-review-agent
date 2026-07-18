from __future__ import annotations

import contextlib
import gc
import json
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator


ROOT = Path(__file__).resolve().parents[3]
LOCK_DIR = ROOT / ".runtime" / "gpu-gate"
LOCK_PATH = LOCK_DIR / "e-review-gpu.lock"


@dataclass
class GpuProcess:
    pid: int | None
    process_name: str
    used_gpu_memory_mb: int | None
    gpu_uuid: str | None = None


class GpuDriverMode(str, Enum):
    WDDM = "WDDM"
    TCC = "TCC"
    UNKNOWN = "UNKNOWN"


class GpuGatePolicyMode(str, Enum):
    STRICT = "strict"
    WDDM_AWARE = "wddm-aware"
    AUTO = "auto"


@dataclass
class GpuStatus:
    ok: bool
    gpu_name: str = ""
    gpu_uuid: str = ""
    utilization_percent: int | None = None
    memory_used_mb: int | None = None
    memory_free_mb: int | None = None
    memory_total_mb: int | None = None
    driver_mode: GpuDriverMode = GpuDriverMode.UNKNOWN
    foreign_processes: list[GpuProcess] | None = None
    wddm_graphics_process_count: int = 0
    error: str | None = None

    @property
    def foreign_process_count(self) -> int:
        return len(self.foreign_processes or [])


@dataclass
class GpuGateDecision:
    decision: str
    allowed: bool
    driver_mode: GpuDriverMode
    policy_mode: GpuGatePolicyMode
    reason_codes: list[str]
    numeric_compute_process_count: int
    free_memory_mb: int | None
    free_memory_drop_mb: int
    total_gpu_utilization: int | None
    graphics_activity_tolerated: bool
    valid_external_lock_count: int
    stable_check_count: int
    checked_at: str


def _run_nvidia_smi(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["nvidia-smi", *args], capture_output=True, text=True, check=False)


def _parse_int(value: str) -> int | None:
    value = value.strip()
    if not value or value.upper() == "N/A":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def query_gpu_status(current_pid: int | None = None, runner: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_nvidia_smi) -> GpuStatus:
    gpu = runner(
        [
            "--query-gpu=index,uuid,name,utilization.gpu,memory.used,memory.free,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    if gpu.returncode != 0:
        return GpuStatus(ok=False, error=(gpu.stderr or gpu.stdout or "nvidia-smi failed").strip())
    line = (gpu.stdout or "").splitlines()[0] if (gpu.stdout or "").splitlines() else ""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 7:
        return GpuStatus(ok=False, error=f"unexpected nvidia-smi gpu output: {line}")

    driver_mode = _query_driver_mode(runner)

    processes: list[GpuProcess] = []
    wddm_graphics_process_count = 0
    proc = runner(
        [
            "--query-compute-apps=pid,process_name,used_gpu_memory,gpu_uuid",
            "--format=csv,noheader,nounits",
        ]
    )
    if proc.returncode == 0:
        for raw in (proc.stdout or "").splitlines():
            if not raw.strip():
                continue
            fields = [part.strip() for part in raw.split(",")]
            pid = _parse_int(fields[0]) if fields else None
            if current_pid is not None and pid == current_pid:
                continue
            used_memory = _parse_int(fields[2]) if len(fields) > 2 else None
            if used_memory is None:
                wddm_graphics_process_count += 1
                continue
            processes.append(
                GpuProcess(
                    pid=pid,
                    process_name=fields[1] if len(fields) > 1 else "",
                    used_gpu_memory_mb=used_memory,
                    gpu_uuid=fields[3] if len(fields) > 3 else None,
                )
            )

    return GpuStatus(
        ok=True,
        gpu_uuid=parts[1],
        gpu_name=parts[2],
        utilization_percent=_parse_int(parts[3]),
        memory_used_mb=_parse_int(parts[4]),
        memory_free_mb=_parse_int(parts[5]),
        memory_total_mb=_parse_int(parts[6]),
        driver_mode=driver_mode,
        foreign_processes=processes,
        wddm_graphics_process_count=wddm_graphics_process_count,
    )


def _query_driver_mode(runner: Callable[[list[str]], subprocess.CompletedProcess[str]]) -> GpuDriverMode:
    direct = runner(["--query-gpu=driver_model.current", "--format=csv,noheader"])
    if direct.returncode == 0:
        text = (direct.stdout or "").strip().splitlines()
        if text:
            return _parse_driver_mode(text[0])
    detailed = runner(["-q"])
    if detailed.returncode == 0:
        for raw in (detailed.stdout or "").splitlines():
            if "Current" in raw and ("WDDM" in raw.upper() or "TCC" in raw.upper()):
                return _parse_driver_mode(raw)
    return GpuDriverMode.UNKNOWN


def _parse_driver_mode(value: str) -> GpuDriverMode:
    text = value.upper()
    if "WDDM" in text:
        return GpuDriverMode.WDDM
    if "TCC" in text:
        return GpuDriverMode.TCC
    return GpuDriverMode.UNKNOWN


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_lock(path: Path | None = None) -> dict | None:
    path = path or LOCK_PATH
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"pid": None, "stage": "unreadable"}


def clear_stale_lock(path: Path | None = None) -> bool:
    path = path or LOCK_PATH
    lock = read_lock(path)
    if not lock:
        return False
    pid = lock.get("pid")
    if isinstance(pid, int) and is_pid_alive(pid):
        return False
    path.unlink(missing_ok=True)
    return True


def acquire_lock(stage: str, gpu_uuid: str = "", python_executable: str = "", path: Path | None = None) -> None:
    path = path or LOCK_PATH
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    clear_stale_lock(path)
    payload = {
        "pid": os.getpid(),
        "stage": stage,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gpu_uuid": gpu_uuid,
        "python_executable": python_executable,
    }
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(path), flags)
    try:
        os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    finally:
        os.close(fd)


def release_lock(path: Path | None = None) -> None:
    path = path or LOCK_PATH
    lock = read_lock(path)
    if lock and lock.get("pid") == os.getpid():
        path.unlink(missing_ok=True)


def evaluate_gate(
    status: GpuStatus,
    min_free_memory_mb: int = 6000,
    gpu_gate_mode: str | GpuGatePolicyMode = GpuGatePolicyMode.AUTO,
    max_wddm_total_utilization: int = 60,
    max_free_memory_drop_mb: int = 256,
    require_zero_numeric_compute_processes: bool = True,
    allow_wddm_graphics_activity: bool = True,
    memory_free_samples: list[int] | None = None,
    stable_check_count: int = 1,
) -> GpuGateDecision:
    requested_policy = GpuGatePolicyMode(gpu_gate_mode)
    policy = _resolve_policy_mode(status.driver_mode, gpu_gate_mode)
    reasons: list[str] = []
    if not status.ok:
        reasons.append("GPU_STATUS_CHECK_BLOCKED")
        return _decision(status, policy, "blocked_gpu_error", reasons, 0, memory_free_samples, False, stable_check_count)

    numeric_count = status.foreign_process_count
    if require_zero_numeric_compute_processes and numeric_count:
        reasons.append("GPU_NUMERIC_COMPUTE_PROCESS_PRESENT")
    if status.memory_free_mb is None or status.memory_free_mb < min_free_memory_mb:
        reasons.append("GPU_MEMORY_INSUFFICIENT")

    free_drop = _free_memory_drop(memory_free_samples)
    if free_drop > max_free_memory_drop_mb:
        reasons.append("GPU_MEMORY_DECLINING")

    lock = read_lock()
    if lock and lock.get("pid") != os.getpid() and isinstance(lock.get("pid"), int) and is_pid_alive(lock["pid"]):
        reasons.append("GPU_EXTERNAL_LOCK_PRESENT")

    graphics_tolerated = False
    if policy == GpuGatePolicyMode.WDDM_AWARE:
        if status.utilization_percent is None:
            reasons.append("GPU_STATUS_CHECK_BLOCKED")
        elif status.utilization_percent > max_wddm_total_utilization:
            reasons.append("GPU_UTILIZATION_EXTREME")
        elif allow_wddm_graphics_activity and status.utilization_percent > 10:
            graphics_tolerated = True
            reasons.append("GPU_WDDM_GRAPHICS_ACTIVITY_TOLERATED")
        if status.driver_mode == GpuDriverMode.UNKNOWN:
            reasons.append("GPU_DRIVER_MODE_UNKNOWN")
    else:
        if status.utilization_percent is None or status.utilization_percent > 20:
            reasons.append("GPU_UTILIZATION_BUSY")
        if (
            policy == GpuGatePolicyMode.STRICT
            and status.driver_mode == GpuDriverMode.UNKNOWN
            and requested_policy == GpuGatePolicyMode.AUTO
        ):
            reasons.append("GPU_DRIVER_MODE_UNKNOWN")

    positive = []
    if not numeric_count:
        positive.append("GPU_NO_NUMERIC_COMPUTE_PROCESS")
    if status.memory_free_mb is not None and status.memory_free_mb >= min_free_memory_mb:
        positive.append("GPU_FREE_MEMORY_SUFFICIENT")
    if free_drop <= max_free_memory_drop_mb:
        positive.append("GPU_FREE_MEMORY_STABLE")
    hard_reasons = {
        "GPU_STATUS_CHECK_BLOCKED",
        "GPU_NUMERIC_COMPUTE_PROCESS_PRESENT",
        "GPU_MEMORY_INSUFFICIENT",
        "GPU_MEMORY_DECLINING",
        "GPU_EXTERNAL_LOCK_PRESENT",
        "GPU_UTILIZATION_EXTREME",
        "GPU_UTILIZATION_BUSY",
        "GPU_DRIVER_MODE_UNKNOWN",
    }
    blocked = any(reason in hard_reasons for reason in reasons)
    decision = "allowed"
    if blocked:
        if "GPU_NUMERIC_COMPUTE_PROCESS_PRESENT" in reasons:
            decision = "blocked_compute_process"
        elif "GPU_MEMORY_INSUFFICIENT" in reasons or "GPU_MEMORY_DECLINING" in reasons:
            decision = "blocked_memory"
        elif "GPU_EXTERNAL_LOCK_PRESENT" in reasons:
            decision = "blocked_lock"
        elif "GPU_DRIVER_MODE_UNKNOWN" in reasons:
            decision = "blocked_unknown_driver_mode"
        elif "GPU_UTILIZATION_EXTREME" in reasons or "GPU_UTILIZATION_BUSY" in reasons:
            decision = "blocked_high_utilization"
        else:
            decision = "blocked_gpu_error"
    return GpuGateDecision(
        decision=decision,
        allowed=not blocked,
        driver_mode=status.driver_mode,
        policy_mode=policy,
        reason_codes=positive + reasons,
        numeric_compute_process_count=numeric_count,
        free_memory_mb=status.memory_free_mb,
        free_memory_drop_mb=free_drop,
        total_gpu_utilization=status.utilization_percent,
        graphics_activity_tolerated=graphics_tolerated,
        valid_external_lock_count=1 if "GPU_EXTERNAL_LOCK_PRESENT" in reasons else 0,
        stable_check_count=stable_check_count,
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def evaluate_busy(status: GpuStatus, min_free_memory_mb: int = 6000) -> tuple[bool, list[str]]:
    decision = evaluate_gate(status, min_free_memory_mb=min_free_memory_mb, gpu_gate_mode=GpuGatePolicyMode.STRICT)
    legacy_reasons = []
    for reason in decision.reason_codes:
        legacy_reasons.append({
            "GPU_NUMERIC_COMPUTE_PROCESS_PRESENT": "FOREIGN_COMPUTE_PROCESS",
            "GPU_MEMORY_INSUFFICIENT": "GPU_MEMORY_BUSY",
            "GPU_EXTERNAL_LOCK_PRESENT": "GPU_LOCK_BLOCKED",
        }.get(reason, reason))
    return not decision.allowed, [reason for reason in legacy_reasons if reason not in {"GPU_NO_NUMERIC_COMPUTE_PROCESS", "GPU_FREE_MEMORY_SUFFICIENT", "GPU_FREE_MEMORY_STABLE"}]


def _resolve_policy_mode(driver_mode: GpuDriverMode, mode: str | GpuGatePolicyMode) -> GpuGatePolicyMode:
    requested = GpuGatePolicyMode(mode)
    if requested != GpuGatePolicyMode.AUTO:
        return requested
    if driver_mode == GpuDriverMode.WDDM:
        return GpuGatePolicyMode.WDDM_AWARE
    return GpuGatePolicyMode.STRICT


def _free_memory_drop(samples: list[int] | None) -> int:
    samples = [int(value) for value in (samples or []) if value is not None]
    if len(samples) < 2:
        return 0
    return max(samples) - samples[-1]


def _decision(status, policy, decision, reasons, numeric_count, samples, graphics_tolerated, stable_check_count):
    return GpuGateDecision(
        decision=decision,
        allowed=False,
        driver_mode=status.driver_mode,
        policy_mode=policy,
        reason_codes=reasons,
        numeric_compute_process_count=numeric_count,
        free_memory_mb=status.memory_free_mb,
        free_memory_drop_mb=_free_memory_drop(samples),
        total_gpu_utilization=status.utilization_percent,
        graphics_activity_tolerated=graphics_tolerated,
        valid_external_lock_count=0,
        stable_check_count=stable_check_count,
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


def wait_for_gpu_idle(
    stage: str,
    min_free_memory_mb: int = 6000,
    check_interval_seconds: int = 20,
    stable_checks: int = 3,
    timeout_seconds: int = 0,
    gpu_gate_mode: str | GpuGatePolicyMode = GpuGatePolicyMode.AUTO,
    max_wddm_total_utilization: int = 60,
    max_free_memory_drop_mb: int = 256,
    require_zero_numeric_compute_processes: bool = True,
    allow_wddm_graphics_activity: bool = True,
    status_fn: Callable[[], GpuStatus] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> GpuStatus:
    started = time.time()
    stable = 0
    status_fn = status_fn or (lambda: query_gpu_status(current_pid=os.getpid()))
    last_status = GpuStatus(ok=False, error="not checked")
    free_samples: list[int] = []
    while True:
        last_status = status_fn()
        if last_status.memory_free_mb is not None:
            free_samples.append(last_status.memory_free_mb)
            free_samples = free_samples[-stable_checks:]
        decision = evaluate_gate(
            last_status,
            min_free_memory_mb=min_free_memory_mb,
            gpu_gate_mode=gpu_gate_mode,
            max_wddm_total_utilization=max_wddm_total_utilization,
            max_free_memory_drop_mb=max_free_memory_drop_mb,
            require_zero_numeric_compute_processes=require_zero_numeric_compute_processes,
            allow_wddm_graphics_activity=allow_wddm_graphics_activity,
            memory_free_samples=free_samples,
            stable_check_count=stable + 1,
        )
        if decision.allowed:
            stable += 1
            if stable >= stable_checks:
                if decision.graphics_activity_tolerated:
                    print("GPU_WDDM_GRAPHICS_ACTIVITY_TOLERATED")
                print("GPU_IDLE_GATE_PASS")
                return last_status
        else:
            stable = 0
            elapsed = int(time.time() - started)
            print("GPU_BUSY_WAITING")
            print(f"stage={stage}")
            print(f"gpu={last_status.gpu_name}")
            print(f"utilization={last_status.utilization_percent}")
            print(f"memory_used={last_status.memory_used_mb}")
            print(f"memory_free={last_status.memory_free_mb}")
            print(f"foreign_process_count={last_status.foreign_process_count}")
            print(f"wddm_graphics_process_count={last_status.wddm_graphics_process_count}")
            print(f"elapsed_wait_seconds={elapsed}")
            print(f"next_check_seconds={check_interval_seconds}")
            print(f"driver_mode={decision.driver_mode.value}")
            print(f"policy_mode={decision.policy_mode.value}")
            print(f"decision={decision.decision}")
            print(f"reasons={','.join(decision.reason_codes)}")
        if timeout_seconds and (time.time() - started) >= timeout_seconds:
            print("GPU_WAIT_TIMEOUT_BLOCKED")
            raise TimeoutError("GPU_WAIT_TIMEOUT_BLOCKED")
        sleep_fn(check_interval_seconds)


@contextlib.contextmanager
def gpu_exclusive_gate(
    stage: str,
    min_free_memory_mb: int = 6000,
    check_interval_seconds: int = 20,
    stable_checks: int = 3,
    timeout_seconds: int = 0,
    gpu_gate_mode: str | GpuGatePolicyMode = GpuGatePolicyMode.AUTO,
    max_wddm_total_utilization: int = 60,
    max_free_memory_drop_mb: int = 256,
    require_zero_numeric_compute_processes: bool = True,
    allow_wddm_graphics_activity: bool = True,
) -> Iterator[GpuStatus]:
    status = wait_for_gpu_idle(
        stage=stage,
        min_free_memory_mb=min_free_memory_mb,
        check_interval_seconds=check_interval_seconds,
        stable_checks=stable_checks,
        timeout_seconds=timeout_seconds,
        gpu_gate_mode=gpu_gate_mode,
        max_wddm_total_utilization=max_wddm_total_utilization,
        max_free_memory_drop_mb=max_free_memory_drop_mb,
        require_zero_numeric_compute_processes=require_zero_numeric_compute_processes,
        allow_wddm_graphics_activity=allow_wddm_graphics_activity,
    )
    acquire_lock(stage=stage, gpu_uuid=status.gpu_uuid, python_executable=os.environ.get("PYTHON", ""))
    print("GPU_EXCLUSIVE_LOCK_ACQUIRED")
    try:
        status = wait_for_gpu_idle(
            stage=f"{stage}-locked-confirm",
            min_free_memory_mb=min_free_memory_mb,
            check_interval_seconds=check_interval_seconds,
            stable_checks=1,
            timeout_seconds=timeout_seconds,
            gpu_gate_mode=gpu_gate_mode,
            max_wddm_total_utilization=max_wddm_total_utilization,
            max_free_memory_drop_mb=max_free_memory_drop_mb,
            require_zero_numeric_compute_processes=require_zero_numeric_compute_processes,
            allow_wddm_graphics_activity=allow_wddm_graphics_activity,
        )
        yield status
    finally:
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                with contextlib.suppress(Exception):
                    torch.cuda.ipc_collect()
        except Exception:
            pass
        release_lock()
        print("GPU_EXCLUSIVE_LOCK_RELEASED")
