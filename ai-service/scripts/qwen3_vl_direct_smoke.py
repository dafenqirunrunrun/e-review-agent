import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = ROOT / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.vlm.qwen3_vl_runtime import Qwen3VlRuntime, Qwen3VlRuntimeRequest
from app.vlm.schema_repair import parse_or_repair_visual_schema


RUNTIME = ROOT / ".runtime" / "vlm-smoke"
OUT = RUNTIME / "qwen3_vl_direct_smoke_result.json"


def write_result(payload: dict):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def blocked(marker: str, **extra) -> int:
    payload = {"marker": marker, **extra}
    write_result(payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(marker)
    return 2


def main() -> int:
    model_dir = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct"))
    image = Path(
        os.getenv(
            "E_REVIEW_VLM_DIRECT_IMAGE",
            str(ROOT / ".runtime" / "vlm-smoke" / "images" / "vlm-smoke-02-dented-box.png"),
        )
    )
    if not model_dir.exists() or not (model_dir / "config.json").exists():
        return blocked("VLM_DIRECT_INFERENCE_BLOCKED_MODEL_NOT_READY", model_dir=str(model_dir), image=str(image))
    if not image.exists():
        return blocked("VLM_DIRECT_INFERENCE_BLOCKED_IMAGE_MISSING", model_dir=str(model_dir), image=str(image))

    prompt = (
        "Only describe visible evidence in the image. Return strict JSON with fields: "
        "image_available, image_quality, visual_findings, visual_evidence, "
        "text_image_consistency, visual_risk_level, need_human_review, missing_information. "
        "Use uncertain when unsure."
    )
    result = Qwen3VlRuntime().run(
        Qwen3VlRuntimeRequest(
            image_paths=[str(image)],
            prompt=prompt,
            model_dir=model_dir,
            max_new_tokens=48,
            do_sample=False,
            stage="qwen3-vl-direct-smoke",
            unload_after_request=True,
            min_free_memory_mb=int(os.getenv("E_REVIEW_GPU_MIN_FREE_MB", "5200")),
            check_interval_seconds=int(os.getenv("E_REVIEW_GPU_CHECK_INTERVAL_SECONDS", "30")),
            stable_checks=int(os.getenv("E_REVIEW_GPU_IDLE_STABLE_CHECKS", "3")),
            timeout_seconds=int(os.getenv("E_REVIEW_GPU_WAIT_TIMEOUT_SECONDS", "14400")),
        )
    )

    schema_valid = False
    repair_meta = {
        "raw_schema_valid": False,
        "repair_used": False,
        "repaired_schema_valid": False,
        "repair_reason": None,
    }
    if result.raw_text.strip():
        try:
            _, repair_meta = parse_or_repair_visual_schema(result.raw_text)
            schema_valid = repair_meta["raw_schema_valid"] or repair_meta["repaired_schema_valid"]
        except Exception as exc:
            repair_meta["repair_reason"] = type(exc).__name__

    marker = (
        "VLM_DIRECT_INFERENCE_PASS"
        if result.real_inference and result.cuda_used and not result.fallback_used and result.generate_executed and schema_valid
        else "VLM_DIRECT_INFERENCE_FAIL"
    )
    if result.error_code == "CUDA_OUT_OF_MEMORY":
        marker = "VLM_DIRECT_INFERENCE_BLOCKED_OOM"
    elif result.error_code == "GPU_WAIT_TIMEOUT":
        marker = "VLM_DIRECT_INFERENCE_BLOCKED_GPU_WAIT_TIMEOUT"
    elif result.error_code:
        marker = "VLM_DIRECT_INFERENCE_BLOCKED"

    payload = {
        "marker": marker,
        "real_inference": result.real_inference,
        "cuda_used": result.cuda_used,
        "fallback_used": result.fallback_used,
        "generate_executed": result.generate_executed,
        "model_dir": str(model_dir),
        "image": str(image),
        "dtype": result.dtype,
        "device_map_used": result.device_map_used,
        "manual_to_cuda_used": result.manual_to_cuda_used,
        "accelerate_available": result.accelerate_available,
        "gpu_memory_budget_mb": result.gpu_memory_budget_mb,
        "stable_free_memory_mb": result.stable_free_memory_mb,
        "local_files_only": result.local_files_only,
        "batch_size": result.batch_size,
        "max_new_tokens": result.max_new_tokens,
        "do_sample": result.do_sample,
        "image_size": result.image_size,
        "model_load_ms": result.model_load_ms,
        "inference_ms": result.inference_ms,
        "total_latency_ms": result.total_latency_ms,
        "input_tokens": result.input_token_count,
        "output_tokens": result.output_token_count,
        "gpu_memory_before_load_mb": result.gpu_memory_before_load_mb,
        "gpu_memory_after_load_mb": result.gpu_memory_after_load_mb,
        "gpu_peak_memory_mb": result.gpu_peak_memory_mb,
        "gpu_memory_after_unload_mb": result.gpu_memory_after_unload_mb,
        "raw_output": result.raw_text,
        "schema_valid": schema_valid,
        "gpu_gate_used": True,
        "error_code": result.error_code,
        "error_summary": result.error_summary,
        **repair_meta,
    }
    if payload.get("gpu_memory_after_unload_mb") is not None:
        baseline = result.gpu_memory_before_load_mb or 0
        payload["gpu_memory_release_marker"] = (
            "GPU_MEMORY_RELEASE_PASS"
            if payload["gpu_memory_after_unload_mb"] <= max(2048, baseline + 512)
            else "GPU_MEMORY_NOT_RELEASED_BLOCKED"
        )
    write_result(payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(marker)
    return 0 if marker == "VLM_DIRECT_INFERENCE_PASS" else 5


if __name__ == "__main__":
    raise SystemExit(main())
