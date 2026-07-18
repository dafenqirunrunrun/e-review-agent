import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_qwen_runtime_path_audit_records_existing_cache_without_vlm_loading():
    audit = load_json("data/private_research/audit/qwen_runtime_path_audit.json")

    assert audit["marker"] == "QWEN_RUNTIME_PATH_AUDIT_COMPLETE"
    assert audit["model_dir_ready"] is True
    assert audit["model_dir_label"] == "<repo-external>/models/Qwen3-1.7B"
    assert audit["provider_uses_class_level_runtime_cache"] is True
    assert audit["provider_reloads_model_per_sample_in_same_process"] is False
    assert audit["qwen3_vl_loaded_by_text_path"] is False


def test_qwen_runtime_budget_blocked_does_not_claim_real_inference():
    budget = load_json("data/private_research/audit/qwen_text_runtime_budget_smoke.json")

    assert budget["marker"] in {
        "QWEN_TEXT_RUNTIME_BUDGET_BLOCKED",
        "QWEN_TEXT_RUNTIME_BUDGET_PASS",
        "QWEN_TEXT_WDDM_CANARY_BLOCKED",
        "QWEN_TEXT_WDDM_CANARY_PASS",
    }
    assert budget["formal_benchmark"] is False
    if budget["marker"] == "QWEN_TEXT_RUNTIME_BUDGET_BLOCKED":
        assert budget["real_model_inference_count"] == 0
        assert budget["model_load_count"] == 0
        assert budget["generate_call_count"] == 0
        assert budget["schema_valid_rate"] == 0.0
        assert budget["error_summary"] == "GPU_WAIT_TIMEOUT_BLOCKED"
    if budget["marker"] == "QWEN_TEXT_RUNTIME_BUDGET_PASS":
        assert budget["real_model_inference_count"] == 4
        assert budget["model_load_count"] == 1
        assert budget["generate_call_count"] == 4
        assert budget["fallback_count"] == 0
        assert budget["oom_count"] == 0
        assert budget["unload_success"] is True
    if "gpu_status" in budget:
        assert budget["gpu_status"]["memory_free_mb"] >= 0
    assert "D:\\" not in json.dumps(budget, ensure_ascii=False)
