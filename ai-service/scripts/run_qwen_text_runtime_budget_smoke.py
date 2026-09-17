import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.llm.qwen_text_runtime import (  # noqa: E402
    QwenTextRuntimeCounters,
    QwenTextRuntimeRequest,
    QwenTextRuntimeSession,
)
from app.runtime.gpu_gate import query_gpu_status  # noqa: E402


OUT = ROOT / "data" / "private_research" / "audit" / "qwen_text_runtime_budget_smoke.json"
CANARY_OUT = ROOT / "data" / "private_research" / "eval" / "qwen_text_wddm_canary_summary.json"
BUDGET_OUT = ROOT / "data" / "private_research" / "eval" / "qwen_text_runtime_budget_summary.json"
DOC = ROOT / "docs" / "174_v163_qwen_runtime_path_audit.md"
RUNTIME_DOC = ROOT / "docs" / "179_v1631_qwen_text_wddm_runtime.md"


def _sample_private_rows(seed: int = 163):
    from ai_service_eval_import import sample_rows

    rows, _ = sample_rows(1, 0, seed)
    amazon = [row for row in rows if row.get("source_id") == "amazon_reviews_2023"]
    asap = [row for row in rows if row.get("source_id") == "asap_chinese_reviews"]
    if not amazon or not asap:
        raise RuntimeError("PRIVATE_TEXT_SAMPLE_NOT_AVAILABLE")
    return [amazon[0], asap[0], amazon[0], asap[0]]


def _row_hash(row):
    text = str(row.get("review_text") or row.get("text") or "")
    source = str(row.get("source_id") or "")
    return hashlib.sha256(f"{source}|{text}".encode("utf-8", errors="replace")).hexdigest()[:24]


def _percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * p / 100) - 1))
    return ordered[index]


def _pass_status(summary):
    if (
        summary["real_model_inference_count"] == 4
        and summary["generate_call_count"] == 4
        and summary["model_load_count"] == 1
        and summary["schema_valid_rate"] >= 0.75
        and summary["fallback_count"] == 0
        and summary["empty_output_count"] == 0
        and summary["oom_count"] == 0
        and (summary["avg_active_request_ms"] or 10**9) <= 30000
        and (summary["p95_active_request_ms"] or 10**9) <= 45000
        and summary["unload_success"] is True
    ):
        return "QWEN_TEXT_RUNTIME_BUDGET_PASS"
    return "QWEN_TEXT_RUNTIME_BUDGET_BLOCKED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(ROOT.parent / "models" / "Qwen3-1.7B"))
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--max-input-tokens", type=int, default=1024)
    parser.add_argument("--min-free-memory-mb", type=int, default=5200)
    parser.add_argument("--check-interval-seconds", type=int, default=30)
    parser.add_argument("--stable-checks", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--seed", type=int, default=163)
    parser.add_argument("--gpu-gate-mode", choices=["strict", "wddm-aware", "auto"], default="auto")
    parser.add_argument("--max-wddm-total-utilization", type=int, default=60)
    parser.add_argument("--max-free-memory-drop-mb", type=int, default=256)
    parser.add_argument("--require-zero-numeric-compute-processes", default="true")
    parser.add_argument("--allow-wddm-graphics-activity", default="true")
    parser.add_argument("--canary", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter()
    QwenTextRuntimeCounters.reset()
    rows = _synthetic_canary_rows() if args.canary else _sample_private_rows(args.seed)
    results = []
    model_dir = Path(args.model_dir)
    session = None
    try:
        with QwenTextRuntimeSession(
            model_dir=model_dir,
            stage="qwen-text-runtime-budget-smoke",
            min_free_memory_mb=args.min_free_memory_mb,
            check_interval_seconds=args.check_interval_seconds,
            stable_checks=args.stable_checks,
            timeout_seconds=args.timeout_seconds,
            device_placement="cuda",
            gpu_gate_mode=args.gpu_gate_mode,
            max_wddm_total_utilization=args.max_wddm_total_utilization,
            max_free_memory_drop_mb=args.max_free_memory_drop_mb,
            require_zero_numeric_compute_processes=_bool_arg(args.require_zero_numeric_compute_processes),
            allow_wddm_graphics_activity=_bool_arg(args.allow_wddm_graphics_activity),
        ) as session:
            for row in rows:
                result = session.generate(
                    QwenTextRuntimeRequest(
                        review_text=str(row.get("review_text") or row.get("text") or ""),
                        rating=row.get("rating"),
                        max_new_tokens=args.max_new_tokens,
                        max_input_tokens=args.max_input_tokens,
                        do_sample=False,
                    ),
                    sample_id_hash=_row_hash(row),
                )
                results.append(result)
    except Exception as exc:
        summary = _blocked_summary(args, started, type(exc).__name__, str(exc)[:1000])
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _append_doc(summary)
        print(summary["marker"])
        return
    session_breakdown = {
        "model_unload_ms": getattr(session, "model_unload_ms", None),
        "gpu_memory_after_unload_mb": getattr(session, "gpu_memory_after_unload_mb", None),
        "unload_success": bool(getattr(session, "unload_completed", False)),
        "gpu_memory_before_load_mb": getattr(session, "gpu_memory_before_load_mb", None),
        "gpu_memory_after_load_mb": getattr(session, "gpu_memory_after_load_mb", None),
    }

    generate_ms = [item.latency_breakdown.get("prefill_and_generate_ms") for item in results if item.latency_breakdown.get("prefill_and_generate_ms") is not None]
    active_ms = [item.latency_breakdown.get("active_request_ms") for item in results if item.latency_breakdown.get("active_request_ms") is not None]
    output_tokens = [item.output_token_count for item in results]
    input_tokens = [item.input_token_count for item in results]
    peak_memory = None
    try:
        import torch

        peak_memory = round(torch.cuda.max_memory_reserved(0) / 1024 / 1024, 2) if torch.cuda.is_available() else None
    except Exception:
        pass

    counters = QwenTextRuntimeCounters.snapshot()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": "QWEN_TEXT_RUNTIME_BUDGET_BLOCKED",
        "canary": args.canary,
        "private_exploratory": True,
        "formal_benchmark": False,
        "model_dir_label": "<repo-external>/models/Qwen3-1.7B",
        "max_new_tokens": args.max_new_tokens,
        "max_input_tokens": args.max_input_tokens,
        "do_sample": False,
        "sample_count": len(results),
        "real_model_inference_count": sum(1 for item in results if item.real_inference and item.generate_executed),
        "model_load_count": counters["model_load_count"],
        "tokenizer_load_count": counters["tokenizer_load_count"],
        "generate_call_count": counters["generate_call_count"],
        "unload_count": counters["unload_count"],
        "gpu_lock_acquire_count": counters["gpu_lock_acquire_count"],
        "schema_valid_count": sum(1 for item in results if item.schema_valid),
        "schema_valid_rate": round(sum(1 for item in results if item.schema_valid) / len(results), 4) if results else 0.0,
        "fallback_count": sum(1 for item in results if item.fallback_used),
        "empty_output_count": sum(1 for item in results if not item.raw_output_hash),
        "avg_generate_ms": round(statistics.mean(generate_ms), 2) if generate_ms else None,
        "p95_generate_ms": _percentile(generate_ms, 95),
        "avg_active_request_ms": round(statistics.mean(active_ms), 2) if active_ms else None,
        "p95_active_request_ms": _percentile(active_ms, 95),
        "model_load_ms": results[0].latency_breakdown.get("model_load_ms") if results else None,
        "tokenizer_load_ms": results[0].latency_breakdown.get("tokenizer_load_ms") if results else None,
        "gpu_peak_memory_mb": peak_memory,
        "gpu_memory_after_unload_mb": session_breakdown["gpu_memory_after_unload_mb"],
        "output_token_count": output_tokens,
        "input_token_count": input_tokens,
        "oom_count": sum(1 for item in results if item.error_code == "CUDA_OUT_OF_MEMORY"),
        "unload_success": session_breakdown["unload_success"],
        "latency_breakdown_by_sample": [
            {
                "sample_id_hash": item.sample_id_hash,
                "source_index": index,
                "schema_valid": item.schema_valid,
                "input_token_count": item.input_token_count,
                "output_token_count": item.output_token_count,
                "latency_breakdown": item.latency_breakdown,
                "error_code": item.error_code,
                "error_summary": item.error_summary,
            }
            for index, item in enumerate(results)
        ],
        "runtime_counters": counters,
        "session_breakdown": session_breakdown,
        "total_benchmark_wall_clock_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    summary["marker"] = _canary_status(summary) if args.canary else _pass_status(summary)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target = CANARY_OUT if args.canary else BUDGET_OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_doc(summary)
    print(summary["marker"])


def _append_doc(summary):
    existing = DOC.read_text(encoding="utf-8") if DOC.exists() else "# V1.6.3 Qwen Runtime Path Audit\n\n"
    section = (
        "\n## Runtime Budget Smoke\n\n"
        f"Status: `{summary['marker']}`\n\n"
        f"- real_model_inference_count: `{summary['real_model_inference_count']}`\n"
        f"- model_load_count: `{summary['model_load_count']}`\n"
        f"- tokenizer_load_count: `{summary['tokenizer_load_count']}`\n"
        f"- generate_call_count: `{summary['generate_call_count']}`\n"
        f"- gpu_lock_acquire_count: `{summary['gpu_lock_acquire_count']}`\n"
        f"- schema_valid_rate: `{summary['schema_valid_rate']}`\n"
        f"- avg_generate_ms: `{summary['avg_generate_ms']}`\n"
        f"- p95_generate_ms: `{summary['p95_generate_ms']}`\n"
        f"- avg_active_request_ms: `{summary['avg_active_request_ms']}`\n"
        f"- p95_active_request_ms: `{summary['p95_active_request_ms']}`\n"
        f"- gpu_peak_memory_mb: `{summary['gpu_peak_memory_mb']}`\n"
        f"- unload_success: `{summary['unload_success']}`\n"
    )
    if "## Runtime Budget Smoke" in existing:
        existing = existing.split("## Runtime Budget Smoke", 1)[0].rstrip() + "\n"
    DOC.write_text(existing + section, encoding="utf-8")
    RUNTIME_DOC.write_text(
        "# V1.6.3.1 Qwen Text WDDM Runtime\n\n"
        f"Status: `{summary['marker']}`\n\n"
        f"- canary: `{summary.get('canary')}`\n"
        f"- real_model_inference_count: `{summary['real_model_inference_count']}`\n"
        f"- tokenizer_load_count: `{summary['tokenizer_load_count']}`\n"
        f"- model_load_count: `{summary['model_load_count']}`\n"
        f"- generate_call_count: `{summary['generate_call_count']}`\n"
        f"- schema_valid_rate: `{summary['schema_valid_rate']}`\n"
        f"- avg_active_request_ms: `{summary['avg_active_request_ms']}`\n"
        f"- p95_active_request_ms: `{summary['p95_active_request_ms']}`\n"
        f"- gpu_peak_memory_mb: `{summary['gpu_peak_memory_mb']}`\n"
        f"- unload_success: `{summary['unload_success']}`\n",
        encoding="utf-8",
    )


def _blocked_summary(args, started, error_code, error_summary):
    status = query_gpu_status()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marker": "QWEN_TEXT_WDDM_CANARY_BLOCKED" if args.canary else "QWEN_TEXT_RUNTIME_BUDGET_BLOCKED",
        "canary": args.canary,
        "private_exploratory": True,
        "formal_benchmark": False,
        "model_dir_label": "<repo-external>/models/Qwen3-1.7B",
        "max_new_tokens": args.max_new_tokens,
        "max_input_tokens": args.max_input_tokens,
        "do_sample": False,
        "sample_count": 0,
        "real_model_inference_count": 0,
        "model_load_count": QwenTextRuntimeCounters.snapshot()["model_load_count"],
        "tokenizer_load_count": QwenTextRuntimeCounters.snapshot()["tokenizer_load_count"],
        "generate_call_count": QwenTextRuntimeCounters.snapshot()["generate_call_count"],
        "unload_count": QwenTextRuntimeCounters.snapshot()["unload_count"],
        "gpu_lock_acquire_count": QwenTextRuntimeCounters.snapshot()["gpu_lock_acquire_count"],
        "schema_valid_count": 0,
        "schema_valid_rate": 0.0,
        "fallback_count": 0,
        "empty_output_count": 0,
        "avg_generate_ms": None,
        "p95_generate_ms": None,
        "avg_active_request_ms": None,
        "p95_active_request_ms": None,
        "model_load_ms": None,
        "tokenizer_load_ms": None,
        "gpu_peak_memory_mb": None,
        "gpu_memory_after_unload_mb": None,
        "output_token_count": [],
        "input_token_count": [],
        "oom_count": 0,
        "unload_success": False,
        "blocked_stage": "gpu_gate_or_session_enter",
        "error_code": error_code,
        "error_summary": error_summary,
        "gpu_status": {
            "ok": status.ok,
            "gpu_name": status.gpu_name,
            "utilization_percent": status.utilization_percent,
            "memory_used_mb": status.memory_used_mb,
            "memory_free_mb": status.memory_free_mb,
            "memory_total_mb": status.memory_total_mb,
            "foreign_process_count": status.foreign_process_count,
            "wddm_graphics_process_count": status.wddm_graphics_process_count,
            "error": status.error,
        },
        "latency_breakdown_by_sample": [],
        "runtime_counters": QwenTextRuntimeCounters.snapshot(),
        "session_breakdown": {},
        "total_benchmark_wall_clock_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _synthetic_canary_rows():
    return [
        {
            "source_id": "synthetic_project_owned",
            "review_text": "商品包装有轻微折痕，但商品可以正常使用。",
            "rating": 4,
            "language": "zh",
        }
    ]


def _canary_status(summary):
    if (
        summary["real_model_inference_count"] == 1
        and summary["generate_call_count"] == 1
        and summary["model_load_count"] == 1
        and summary["schema_valid_count"] == 1
        and summary["fallback_count"] == 0
        and summary["empty_output_count"] == 0
        and summary["oom_count"] == 0
        and summary["unload_success"] is True
    ):
        return "QWEN_TEXT_WDDM_CANARY_PASS"
    return "QWEN_TEXT_WDDM_CANARY_BLOCKED"


def _bool_arg(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    # Import through a small alias module path to avoid storing private data in this script.
    helper = ROOT / "ai-service" / "scripts" / "eval_private_real_text_exploratory.py"
    module_text = helper.read_text(encoding="utf-8")
    if "def sample_rows" not in module_text:
        raise RuntimeError("PRIVATE_SAMPLE_HELPER_NOT_AVAILABLE")
    import importlib.util

    spec = importlib.util.spec_from_file_location("ai_service_eval_import", helper)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ai_service_eval_import"] = module
    spec.loader.exec_module(module)
    main()
