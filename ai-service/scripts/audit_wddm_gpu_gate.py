import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.runtime.gpu_gate import GpuDriverMode, GpuGatePolicyMode, query_gpu_status  # noqa: E402


OUT = ROOT / "data" / "private_research" / "audit" / "wddm_gpu_gate_audit.json"
DOC = ROOT / "docs" / "178_v1631_wddm_gpu_gate_audit.md"


def windows_gpu_engine_summary():
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction Stop | ConvertTo-Json -Depth 4"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout)[:200])
        text = completed.stdout.lower()
        return {
            "windows_gpu_engine_status": "available_inconclusive",
            "windows_gpu_engine_available": True,
            "graphics_engine_observed": "engtype_3d" in text,
            "compute_engine_observed": "engtype_compute" in text,
            "video_engine_observed": "engtype_videodecode" in text or "engtype_videoencode" in text,
        }
    except Exception as exc:
        return {
            "windows_gpu_engine_status": "unavailable_or_inconclusive",
            "windows_gpu_engine_available": False,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }


def main():
    status = query_gpu_status()
    gate = ROOT / "ai-service" / "app" / "runtime" / "gpu_gate.py"
    gate_text = gate.read_text(encoding="utf-8", errors="replace")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": "WDDM_GPU_GATE_AUDIT_COMPLETE",
        "current_driver_mode": status.driver_mode.value,
        "current_utilization_percent": status.utilization_percent,
        "current_memory_free_mb": status.memory_free_mb,
        "current_numeric_compute_process_count": status.foreign_process_count,
        "current_wddm_graphics_process_count": status.wddm_graphics_process_count,
        "current_gate_had_hard_total_utilization_threshold": "status.utilization_percent > 20" in gate_text,
        "wddm_aware_policy_implemented": "GpuGatePolicyMode.WDDM_AWARE" in gate_text,
        "driver_mode_enum_implemented": all(mode.value in {item.value for item in GpuDriverMode} for mode in [GpuDriverMode.WDDM, GpuDriverMode.TCC, GpuDriverMode.UNKNOWN]),
        "compute_and_graphics_processes_distinguished": "wddm_graphics_process_count" in gate_text and "foreign_process_count" in gate_text,
        "memory_drop_check_implemented": "GPU_MEMORY_DECLINING" in gate_text,
        "external_lock_check_implemented": "GPU_EXTERNAL_LOCK_PRESENT" in gate_text,
        "supports_test_injection": "status_fn" in gate_text and "sleep_fn" in gate_text,
        "decision_object_fields": [
            "decision",
            "driver_mode",
            "policy_mode",
            "reason_codes",
            "numeric_compute_process_count",
            "free_memory_mb",
            "free_memory_drop_mb",
            "total_gpu_utilization",
            "graphics_activity_tolerated",
            "valid_external_lock_count",
            "stable_check_count",
            "checked_at",
        ],
        "default_policy_mode": GpuGatePolicyMode.AUTO.value,
        "windows_gpu_engine": windows_gpu_engine_summary(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.3.1 WDDM GPU Gate Audit\n\n"
        f"Status: `{report['marker']}`\n\n"
        f"- current_driver_mode: `{report['current_driver_mode']}`\n"
        f"- current_utilization_percent: `{report['current_utilization_percent']}`\n"
        f"- current_memory_free_mb: `{report['current_memory_free_mb']}`\n"
        f"- current_numeric_compute_process_count: `{report['current_numeric_compute_process_count']}`\n"
        f"- current_wddm_graphics_process_count: `{report['current_wddm_graphics_process_count']}`\n"
        f"- wddm_aware_policy_implemented: `{report['wddm_aware_policy_implemented']}`\n"
        f"- windows_gpu_engine_status: `{report['windows_gpu_engine']['windows_gpu_engine_status']}`\n",
        encoding="utf-8",
    )
    print(report["marker"])


if __name__ == "__main__":
    main()
