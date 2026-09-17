import argparse
import sys
from pathlib import Path


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.runtime.gpu_gate import wait_for_gpu_idle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--min-free-memory-mb", type=int, default=6000)
    parser.add_argument("--check-interval-seconds", type=int, default=20)
    parser.add_argument("--stable-checks", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--gpu-gate-mode", choices=["strict", "wddm-aware", "auto"], default="auto")
    parser.add_argument("--max-wddm-total-utilization", type=int, default=60)
    parser.add_argument("--max-free-memory-drop-mb", type=int, default=256)
    parser.add_argument("--require-zero-numeric-compute-processes", default="true")
    parser.add_argument("--allow-wddm-graphics-activity", default="true")
    args = parser.parse_args()
    try:
        wait_for_gpu_idle(
            stage=args.stage,
            min_free_memory_mb=args.min_free_memory_mb,
            check_interval_seconds=args.check_interval_seconds,
            stable_checks=args.stable_checks,
            timeout_seconds=args.timeout_seconds,
            gpu_gate_mode=args.gpu_gate_mode,
            max_wddm_total_utilization=args.max_wddm_total_utilization,
            max_free_memory_drop_mb=args.max_free_memory_drop_mb,
            require_zero_numeric_compute_processes=_bool_arg(args.require_zero_numeric_compute_processes),
            allow_wddm_graphics_activity=_bool_arg(args.allow_wddm_graphics_activity),
        )
        return 0
    except TimeoutError:
        return 2
    except Exception as exc:
        print("GPU_STATUS_CHECK_BLOCKED")
        print(f"error={type(exc).__name__}: {exc}")
        return 3


def _bool_arg(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())
