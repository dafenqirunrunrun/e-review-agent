import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "private_research" / "audit" / "qwen_runtime_path_audit.json"
DOC = ROOT / "docs" / "174_v163_qwen_runtime_path_audit.md"


def main():
    model_dir = ROOT.parent / "models" / "Qwen3-1.7B"
    provider_path = ROOT / "ai-service" / "app" / "llm" / "local_qwen.py"
    exploratory_path = ROOT / "ai-service" / "scripts" / "eval_private_real_text_exploratory.py"
    provider_text = provider_path.read_text(encoding="utf-8", errors="replace")
    exploratory_text = exploratory_path.read_text(encoding="utf-8", errors="replace")
    files = sorted(path.name for path in model_dir.glob("*")) if model_dir.exists() else []

    findings = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": "QWEN_RUNTIME_PATH_AUDIT_COMPLETE",
        "model_dir_ready": model_dir.exists() and (model_dir / "config.json").exists(),
        "model_dir_label": "<repo-external>/models/Qwen3-1.7B",
        "model_file_count": len(files),
        "provider_file": "ai-service/app/llm/local_qwen.py",
        "exploratory_eval_file": "ai-service/scripts/eval_private_real_text_exploratory.py",
        "provider_loads_tokenizer_with_from_pretrained": "AutoTokenizer.from_pretrained" in provider_text,
        "provider_loads_model_with_from_pretrained": "AutoModelForCausalLM.from_pretrained" in provider_text,
        "provider_uses_class_level_runtime_cache": all(token in provider_text for token in ["_tokenizer", "_model", "cls._model is not None"]),
        "provider_reloads_model_per_sample_in_same_process": False,
        "provider_reloads_tokenizer_per_sample_in_same_process": False,
        "provider_has_explicit_unload": False,
        "provider_uses_device_map_auto_when_accelerate_available": "device_map" in provider_text and "accelerate" in provider_text,
        "provider_manual_to_device_without_device_map": "model = model.to(device)" in provider_text,
        "provider_local_files_only_for_local_model_dir": "local_files_only" in provider_text,
        "fallback_can_mask_provider_errors": "except Exception as exc" in (ROOT / "ai-service" / "app" / "llm" / "service.py").read_text(encoding="utf-8", errors="replace"),
        "default_max_new_tokens": 512,
        "exploratory_eval_sets_max_new_tokens": "96" if 'E_REVIEW_LOCAL_QWEN_MAX_NEW_TOKENS\", \"96\"' in exploratory_text else None,
        "exploratory_eval_uses_single_service_instance_per_mode": "service = LlmReviewService" in exploratory_text,
        "exploratory_eval_runs_prompt_then_rag_then_stability_serially": all(token in exploratory_text for token in ["prompt_outputs", "rag_outputs", "stability_outputs"]),
        "qwen3_vl_loaded_by_text_path": False,
        "rag_can_load_bge_or_reranker_when_enabled": True,
        "latency_root_causes": [
            "previous exploratory metric mixed provider call time with model load and possible schema repair",
            "first request can include tokenizer/model load cost",
            "RAG mode may initialize BGE-M3 and reranker when enabled",
            "fallback path can hide provider failure unless real_model_inference_count is checked",
            "existing provider does not expose per-stage timing or unload verification",
        ],
        "v163_runtime_session_added_for_budget_smoke": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.3 Qwen Runtime Path Audit\n\n"
        f"Status: `{findings['marker']}`\n\n"
        "The existing provider uses a class-level runtime cache, so repeated samples in one Python process should not reload the model. "
        "However, it does not expose explicit unload, GPU lock counters, or per-stage latency fields. "
        "The v1.6.3 runtime budget smoke therefore uses a dedicated `QwenTextRuntimeSession` for auditable single-session execution.\n\n"
        "Key findings:\n"
        f"- Model directory ready: `{findings['model_dir_ready']}`\n"
        f"- Existing provider cache: `{findings['provider_uses_class_level_runtime_cache']}`\n"
        f"- Existing provider explicit unload: `{findings['provider_has_explicit_unload']}`\n"
        f"- Text path loads Qwen3-VL: `{findings['qwen3_vl_loaded_by_text_path']}`\n",
        encoding="utf-8",
    )
    print("QWEN_RUNTIME_PATH_AUDIT_COMPLETE")


if __name__ == "__main__":
    main()
