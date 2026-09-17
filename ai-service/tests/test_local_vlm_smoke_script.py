import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "ai-service") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai-service"))

from scripts.eval_local_vlm_smoke import build_session_latency_metrics, classify_session_marker


def _base_12_image_metrics(**overrides):
    metrics = {
        "real_vlm_inference_count": 12,
        "visual_schema_valid_rate": 1.0,
        "fallback_rate": 0,
        "oom_count": 0,
        "model_load_count": 1,
        "processor_load_count": 1,
        "gpu_lock_acquire_count": 1,
        "unload_count": 1,
        "avg_generate_ms": 2200.0,
        "p95_generate_ms": 2600.0,
        "avg_end_to_end_ms": 2300.0,
        "p95_end_to_end_ms": 2700.0,
        "active_session_wall_clock_ms": 40000.0,
        "uncontended": True,
        "second_generate_count": 0,
    }
    metrics.update(overrides)
    return metrics


def test_gpu_wait_is_not_counted_in_active_session_wall_clock():
    breakdowns = [
        {
            "gpu_wait_ms": 453000,
            "gpu_lock_acquire_ms": 453000,
            "processor_load_ms": 1000,
            "model_load_ms": 5000,
            "generate_ms": 2000,
            "total_request_ms": 2200,
            "model_unload_ms": 0,
        },
        {
            "generate_ms": 2100,
            "total_request_ms": 2300,
            "model_unload_ms": 300,
        },
    ]

    metrics = build_session_latency_metrics(breakdowns, total_wall_clock_ms=470000)

    assert metrics["gpu_wait_ms"] == 453000
    assert metrics["active_session_wall_clock_ms"] == 10800
    assert metrics["benchmark_total_wall_clock_ms"] == 470000


def test_external_gpu_contention_outputs_deferred_not_failure():
    metrics = _base_12_image_metrics(uncontended=False, gpu_wait_ms=30000)

    classification = classify_session_marker(metrics, total=12)

    assert classification["correctness_marker"] == "VLM_PROVIDER_SESSION_CORRECTNESS_PASS"
    assert classification["latency_marker"] == "VLM_PROVIDER_LATENCY_DEFERRED_GPU_CONTENTION"
    assert classification["active_latency_marker"] == "VLM_PROVIDER_ACTIVE_LATENCY_PASS"
    assert classification["total_wall_clock_marker"] == "VLM_PROVIDER_TOTAL_WALL_CLOCK_DEFERRED_GPU_CONTENTION"


def test_total_wall_target_is_judged_only_when_uncontended():
    metrics = _base_12_image_metrics(uncontended=True, active_session_wall_clock_ms=350000)

    classification = classify_session_marker(metrics, total=12)

    assert classification["latency_marker"] == "VLM_PROVIDER_LATENCY_TARGET_NOT_MET"


def test_correctness_pass_is_independent_from_latency_pass():
    metrics = _base_12_image_metrics(uncontended=True, avg_generate_ms=16000)

    classification = classify_session_marker(metrics, total=12)

    assert classification["correctness_pass"] is True
    assert classification["correctness_marker"] == "VLM_PROVIDER_SESSION_CORRECTNESS_PASS"
    assert classification["active_latency_pass"] is False
    assert classification["latency_marker"] == "VLM_PROVIDER_LATENCY_TARGET_NOT_MET"


def test_gpu_wait_ratio_over_ten_percent_marks_contended():
    metrics = build_session_latency_metrics(
        [{"gpu_wait_ms": 11000, "gpu_lock_acquire_ms": 11000, "model_load_ms": 1000, "total_request_ms": 1000}],
        total_wall_clock_ms=100000,
    )

    assert metrics["gpu_wait_ratio"] == 0.11
    assert metrics["uncontended"] is False


def test_raw_schema_valid_rate_and_repair_do_not_require_second_generate():
    metrics = _base_12_image_metrics(
        raw_schema_valid_rate=0.25,
        repair_used_rate=1.0,
        deterministic_normalization_rate=1.0,
        second_generate_count=0,
    )

    classification = classify_session_marker(metrics, total=12)

    assert metrics["raw_schema_valid_rate"] == 0.25
    assert metrics["repair_used_rate"] == 1.0
    assert metrics["second_generate_count"] == 0
    assert classification["correctness_marker"] == "VLM_PROVIDER_SESSION_CORRECTNESS_PASS"


def test_local_vlm_smoke_records_blocked_without_real_inference():
    env = os.environ.copy()
    env["E_REVIEW_VLM_MODEL_DIR"] = str(ROOT / ".runtime" / "pytest-missing-qwen3-vl")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "ai-service/scripts/eval_local_vlm_smoke.py")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert "VLM_PROVIDER_SMOKE_BLOCKED" in completed.stdout
    assert "VLM_PROVIDER_SMOKE_PASS" not in completed.stdout
    result = json.loads((ROOT / "data/multimodal/eval/local_vlm_smoke_results.json").read_text(encoding="utf-8"))
    assert result["marker"] == "VLM_PROVIDER_SMOKE_BLOCKED"
    assert result["metrics"]["total_samples"] == 12
    assert result["metrics"]["real_vlm_inference_count"] == 0
    assert "NO_REAL_TRANSFORMERS_VLM_INFERENCE_RECORDED" in result["blocking_reasons"]
    assert result["forbidden_success_markers_emitted"] is False
