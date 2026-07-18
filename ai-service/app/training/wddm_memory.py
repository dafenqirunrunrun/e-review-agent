from __future__ import annotations

import gc
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.runtime.gpu_gate import GpuStatus, query_gpu_status, read_lock


WARNING_FREE_MEMORY_MB = 300
SUSTAINED_LOW_FREE_MEMORY_MB = 200
EMERGENCY_FREE_MEMORY_MB = 128
RESERVED_GROWTH_HARD_MB = 256


@dataclass
class MemorySentinelDecision:
    action: str
    reason: str
    samples: list[dict[str, Any]]

    @property
    def should_stop(self) -> bool:
        return self.action == "stop"


def cuda_memory_snapshot(stage: str, optimizer_step: int | None = None, note: str | None = None) -> dict[str, Any]:
    import torch

    free_bytes = total_bytes = None
    if torch.cuda.is_available():
        free_bytes, total_bytes = torch.cuda.mem_get_info()
    status = query_gpu_status(current_pid=os.getpid())
    allocated = torch.cuda.memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0.0
    reserved = torch.cuda.memory_reserved() / 1024 / 1024 if torch.cuda.is_available() else 0.0
    peak_allocated = torch.cuda.max_memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0.0
    peak_reserved = torch.cuda.max_memory_reserved() / 1024 / 1024 if torch.cuda.is_available() else 0.0
    global_free = status.memory_free_mb
    total_mb = status.memory_total_mb or (round(total_bytes / 1024 / 1024, 2) if total_bytes is not None else None)
    estimated_non_torch = None
    if total_mb is not None and global_free is not None:
        estimated_non_torch = round(float(total_mb) - float(global_free) - reserved, 2)
    return {
        "stage": stage,
        "optimizer_step": optimizer_step,
        "note": note,
        "timestamp_ms": int(time.time() * 1000),
        "torch_process_allocated_mb": round(allocated, 2),
        "torch_process_reserved_mb": round(reserved, 2),
        "torch_peak_allocated_mb": round(peak_allocated, 2),
        "torch_peak_reserved_mb": round(peak_reserved, 2),
        "cuda_mem_get_info_free_mb": round(free_bytes / 1024 / 1024, 2) if free_bytes is not None else None,
        "device_global_free_mb": global_free,
        "nvidia_smi_used_mb": status.memory_used_mb,
        "gpu_utilization": status.utilization_percent,
        "external_numeric_compute_process_count": status.foreign_process_count,
        "wddm_graphics_process_count": status.wddm_graphics_process_count,
        "estimated_non_torch_gpu_usage_mb": estimated_non_torch,
        "wddm_estimate_note": "WDDM approximate",
        "current_pid": os.getpid(),
    }


def cleanup_cuda() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def training_memory_sentinel(
    *,
    current_snapshot: dict[str, Any],
    stable_reserved_baseline_mb: float | None,
    status_fn: Callable[[], GpuStatus] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    cleanup_fn: Callable[[], None] = cleanup_cuda,
    lock_reader: Callable[[], dict[str, Any] | None] = read_lock,
    warning_free_memory_mb: int = WARNING_FREE_MEMORY_MB,
    sustained_low_free_memory_mb: int = SUSTAINED_LOW_FREE_MEMORY_MB,
    emergency_free_memory_mb: int = EMERGENCY_FREE_MEMORY_MB,
    reserved_growth_hard_mb: int = RESERVED_GROWTH_HARD_MB,
) -> MemorySentinelDecision:
    free = current_snapshot.get("device_global_free_mb")
    if free is None or free >= warning_free_memory_mb:
        return MemorySentinelDecision("continue", "TRAINING_MEMORY_OK", [])

    status_fn = status_fn or (lambda: query_gpu_status(current_pid=os.getpid()))
    cleanup_fn()
    samples: list[dict[str, Any]] = []
    for _ in range(3):
        sleep_fn(2)
        status = status_fn()
        sample = {
            "device_global_free_mb": status.memory_free_mb,
            "external_numeric_compute_process_count": status.foreign_process_count,
            "gpu_utilization": status.utilization_percent,
        }
        samples.append(sample)
        if status.foreign_process_count:
            return MemorySentinelDecision("stop", "TRAINING_MEMORY_EXTERNAL_COMPUTE_BLOCKED", samples)

    lock = lock_reader()
    if lock and lock.get("pid") not in {None, os.getpid()}:
        return MemorySentinelDecision("stop", "TRAINING_MEMORY_GPU_LOCK_LOST", samples)

    free_values = [int(sample["device_global_free_mb"]) for sample in samples if sample["device_global_free_mb"] is not None]
    if not free_values:
        return MemorySentinelDecision("warning", "TRAINING_MEMORY_TRANSIENT_LOW_WARNING", samples)
    median_free = statistics.median(free_values)
    if median_free < emergency_free_memory_mb:
        return MemorySentinelDecision("stop", "TRAINING_MEMORY_EMERGENCY_LOW_FREE_BLOCKED", samples)

    reserved = float(current_snapshot.get("torch_process_reserved_mb") or 0.0)
    baseline = float(stable_reserved_baseline_mb or reserved)
    reserved_growth = reserved - baseline
    if all(value < sustained_low_free_memory_mb for value in free_values) and reserved_growth > reserved_growth_hard_mb:
        return MemorySentinelDecision("stop", "TRAINING_MEMORY_SUSTAINED_LOW_WITH_RESERVED_GROWTH_BLOCKED", samples)

    return MemorySentinelDecision("warning", "TRAINING_MEMORY_TRANSIENT_LOW_WARNING", samples)

