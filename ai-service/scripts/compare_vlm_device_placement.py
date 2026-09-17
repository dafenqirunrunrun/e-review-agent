import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = ROOT / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.vlm.qwen3_vl_runtime import Qwen3VlRuntimeCounters, Qwen3VlRuntimeSession
from app.vlm.schema_repair import parse_or_repair_visual_schema


OUT = ROOT / "data" / "multimodal" / "audit" / "vlm_device_placement_comparison.json"
REPORT = ROOT / "docs" / "141_v1614_vlm_device_placement_comparison.md"


def percentile(values: list[float], percent: float):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percent / 100) * (len(ordered) - 1))))
    return ordered[index]


def run_mode(mode: str, model_dir: Path, image: Path) -> dict:
    prompt = (
        "Only describe visible evidence in the image. Return strict JSON with fields: "
        "image_available, image_quality, visual_findings, visual_evidence, "
        "text_image_consistency, visual_risk_level, need_human_review, missing_information. "
        "Use uncertain when unsure."
    )
    Qwen3VlRuntimeCounters.reset()
    attempts = []
    started = time.time()
    try:
        with Qwen3VlRuntimeSession(
            model_dir=model_dir,
            stage=f"vlm-device-placement-{mode}",
            min_free_memory_mb=5200,
            check_interval_seconds=int(os.getenv("E_REVIEW_GPU_CHECK_INTERVAL_SECONDS", "30")),
            stable_checks=int(os.getenv("E_REVIEW_GPU_IDLE_STABLE_CHECKS", "3")),
            timeout_seconds=int(os.getenv("E_REVIEW_GPU_WAIT_TIMEOUT_SECONDS", "14400")),
            device_placement=mode,
        ) as session:
            for index in range(3):
                result = session.generate([str(image)], prompt, max_new_tokens=48, do_sample=False)
                schema_valid = False
                repair_used = False
                if result.raw_text.strip():
                    _, repair_meta = parse_or_repair_visual_schema(result.raw_text)
                    schema_valid = repair_meta["raw_schema_valid"] or repair_meta["repaired_schema_valid"]
                    repair_used = repair_meta["repair_used"]
                attempts.append(
                    {
                        "index": index + 1,
                        "real_inference": result.real_inference,
                        "cuda_used": result.cuda_used,
                        "fallback_used": result.fallback_used,
                        "oom": result.error_code == "CUDA_OUT_OF_MEMORY",
                        "output_schema_valid": schema_valid,
                        "repair_used": repair_used,
                        "model_load_ms": result.model_load_ms,
                        "generate_ms": result.latency_breakdown.get("generate_ms"),
                        "total_request_ms": result.latency_breakdown.get("total_request_ms"),
                        "gpu_peak_memory_mb": result.gpu_peak_memory_mb,
                        "error_code": result.error_code,
                    }
                )
        unload_memory = session.gpu_memory_after_unload_mb
    except Exception as exc:
        unload_memory = None
        attempts.append({"error_code": type(exc).__name__, "error_summary": str(exc)[:1000], "oom": "out of memory" in str(exc).lower()})
    generate = [item.get("generate_ms") for item in attempts if item.get("generate_ms") is not None]
    total = [item.get("total_request_ms") for item in attempts if item.get("total_request_ms") is not None]
    peaks = [item.get("gpu_peak_memory_mb") for item in attempts if item.get("gpu_peak_memory_mb") is not None]
    return {
        "mode": mode,
        "attempts": attempts,
        "metrics": {
            "model_load_ms": next((item.get("model_load_ms") for item in attempts if item.get("model_load_ms") is not None), None),
            "avg_generate_ms": round(statistics.mean(generate), 2) if generate else None,
            "p95_generate_ms": percentile(generate, 95),
            "avg_total_request_ms": round(statistics.mean(total), 2) if total else None,
            "p95_total_request_ms": percentile(total, 95),
            "gpu_peak_memory_mb": max(peaks) if peaks else None,
            "cpu_memory_peak_mb": None,
            "cuda_used": all(item.get("cuda_used") for item in attempts if "cuda_used" in item),
            "oom": any(item.get("oom") for item in attempts),
            "output_schema_valid": all(item.get("output_schema_valid") for item in attempts if "output_schema_valid" in item),
            "wall_clock_ms": round((time.time() - started) * 1000, 2),
            "gpu_memory_after_unload_mb": unload_memory,
            **Qwen3VlRuntimeCounters.snapshot(),
        },
    }


def report(result: dict) -> str:
    return f"""# v1.6.1.4 VLM Device Placement Comparison

## Conclusion

Selected mode: `{result['selected_mode']}`

## Comparison

```json
{json.dumps(result['modes'], ensure_ascii=False, indent=2)}
```

## Selection Rule

The selected mode must avoid OOM, keep schema output valid, preserve at least
400 MB of GPU memory safety margin, and prefer the faster generate path only
when stability is preserved.
"""


def main() -> int:
    if "--child-mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--child-mode") + 1]
        model_dir = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct"))
        image = Path(os.getenv("E_REVIEW_VLM_DIRECT_IMAGE", str(ROOT / ".runtime" / "vlm-smoke" / "images" / "vlm-smoke-01-intact-box.png")))
        print(json.dumps(run_mode(mode, model_dir, image), ensure_ascii=False))
        return 0

    model_dir = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct"))
    image = Path(os.getenv("E_REVIEW_VLM_DIRECT_IMAGE", str(ROOT / ".runtime" / "vlm-smoke" / "images" / "vlm-smoke-01-intact-box.png")))
    if not image.exists():
        subprocess.run([sys.executable, str(ROOT / "ai-service" / "scripts" / "build_vlm_smoke_images.py")], cwd=ROOT, check=True)
    modes = []
    for mode in ["auto", "cuda"]:
        try:
            completed = subprocess.run(
                [sys.executable, str(Path(__file__)), "--child-mode", mode],
                cwd=ROOT,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(os.getenv("E_REVIEW_VLM_DEVICE_COMPARE_TIMEOUT_SECONDS", "600")),
            )
            lines = [line for line in completed.stdout.splitlines() if line.strip().startswith("{")]
            if completed.returncode == 0 and lines:
                modes.append(json.loads(lines[-1]))
            else:
                modes.append(
                    {
                        "mode": mode,
                        "attempts": [{"error_code": "DEVICE_PLACEMENT_CHILD_FAILED", "error_summary": (completed.stderr or completed.stdout)[-1000:]}],
                        "metrics": {"oom": False, "output_schema_valid": False, "timeout": False},
                    }
                )
        except subprocess.TimeoutExpired as exc:
            modes.append(
                {
                    "mode": mode,
                    "attempts": [{"error_code": "DEVICE_PLACEMENT_TIMEOUT", "error_summary": f"timeout after {exc.timeout}s"}],
                    "metrics": {"oom": False, "output_schema_valid": False, "timeout": True},
                }
            )
    safe = [mode for mode in modes if not mode["metrics"]["oom"] and mode["metrics"]["output_schema_valid"]]
    selected = "auto"
    if len(safe) == 2:
        auto, cuda = safe
        auto_generate = auto["metrics"].get("avg_generate_ms") or 10**9
        cuda_generate = cuda["metrics"].get("avg_generate_ms") or 10**9
        selected = "cuda" if cuda_generate < auto_generate and (cuda["metrics"].get("gpu_memory_after_unload_mb") or 9999) <= 2048 else "auto"
    result = {
        "marker": "VLM_DEVICE_PLACEMENT_COMPARISON_COMPLETE",
        "model_dir": str(model_dir),
        "image": str(image),
        "modes": modes,
        "selected_mode": selected,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
