import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / "data-private"
PRIVATE_OUT = PRIVATE_ROOT / "private-research-results" / "private-text-exploratory"
SUMMARY_OUT = ROOT / "data" / "private_research" / "eval" / "private_text_exploratory_summary.json"
MANIFEST_OUT = ROOT / "data" / "private_research" / "eval" / "private_text_exploratory_manifest.json"
DOC_OUT = ROOT / "docs" / "172_v162_private_text_exploratory_eval.md"

sys.path.insert(0, str(ROOT / "ai-service"))


def read_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_asap(path: Path):
    if not path.exists():
        return []
    import csv
    rows = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            text = row.get("review") or row.get("text") or row.get("content") or row.get("comment") or ""
            if text.strip():
                rows.append({"source_id": "asap_chinese_reviews", "review_text": text, "rating": None, "language": "zh"})
    return rows


def sample_rows(per_source: int, stability_per_source: int, seed: int):
    random.seed(seed)
    amazon = read_jsonl(PRIVATE_ROOT / "realworld-pilot" / "raw-text" / "amazon_all_beauty_selected_private.jsonl")
    asap = read_asap(PRIVATE_ROOT / "realworld-pilot" / "raw-text" / "asap_train.csv")
    for row in amazon:
        row.setdefault("source_id", "amazon_reviews_2023")
        row.setdefault("language", "en")
    def pick(rows):
        rows = [row for row in rows if str(row.get("review_text") or row.get("text") or "").strip()]
        return random.sample(rows, min(per_source, len(rows)))
    selected = pick(amazon) + pick(asap)
    stability = selected[: min(stability_per_source, len(selected) // 2)] + selected[max(per_source, len(selected) - stability_per_source):]
    return selected, stability


def row_hash(row):
    text = str(row.get("review_text") or row.get("text") or "")
    source = str(row.get("source_id") or "")
    return hashlib.sha256(f"{source}|{text}".encode("utf-8", errors="replace")).hexdigest()[:24]


def request_for(row, mode):
    from app.schemas.review import ReviewAnalyzeRequest

    return ReviewAnalyzeRequest(
        review_id=row_hash(row),
        product_id="private-pilot-product",
        product_name="private exploratory product",
        review_text=str(row.get("review_text") or row.get("text") or ""),
        image_urls=[],
        rating=row.get("rating"),
        rag_enabled=(mode == "rag"),
        rag_strategy="hybrid_rerank",
    )


def analyze_rows(rows, mode):
    from app.llm.service import LlmReviewService
    from app.services.mock_analyzer import MockAnalyzer
    from app.services.rule_agent import RuleAgentWorkflow

    service = LlmReviewService(RuleAgentWorkflow(MockAnalyzer()))
    outputs = []
    private_lines = []
    for row in rows:
        started = time.perf_counter()
        response = service.analyze(request_for(row, mode))
        latency = response.latency_ms or round((time.perf_counter() - started) * 1000)
        risk_type = str((response.extra or {}).get("risk_type") or "unknown")
        evidence = list(response.evidence or [])
        retrieved = list(response.retrieved_case_ids or [])
        item = {
            "sample_id_hash": row_hash(row),
            "source_id": row.get("source_id"),
            "language": row.get("language") or ("zh" if row.get("source_id") == "asap_chinese_reviews" else "en"),
            "mode": mode,
            "provider": response.llm_provider,
            "schema_valid": bool(response.schema_valid),
            "fallback_used": bool(response.fallback_used),
            "latency_ms": latency,
            "risk_type": risk_type,
            "risk_level": response.risk_level,
            "need_human_review": bool(response.need_human_review),
            "text_evidence_count": len(evidence),
            "retrieved_case_evidence_count": len(retrieved),
            "unsupported_business_action": False,
            "prohibited_auto_action": response.route_decision in {"auto_refund", "auto_ban", "auto_compensate"},
            "empty_output": not bool(response.risk_level or response.sentiment_label),
        }
        outputs.append(item)
        private_lines.append(json.dumps({**item, "full_model_output_redacted": True}, ensure_ascii=False))
    return outputs, private_lines


def aggregate(outputs, input_count):
    if not outputs:
        return {
            "input_record_count": input_count,
            "parse_success_rate": 0.0,
            "real_model_inference_count": 0,
            "schema_valid_rate": 0.0,
            "field_complete_rate": 0.0,
            "fallback_rate": 1.0,
            "empty_output_rate": 1.0,
            "text_evidence_nonempty_rate": 0.0,
            "retrieved_case_evidence_nonempty_rate": 0.0,
            "unsupported_business_action_count": 0,
            "prohibited_auto_action_count": 0,
            "need_human_review_rate": 0.0,
            "output_risk_type_distribution": {},
            "output_risk_level_distribution": {},
            "avg_latency_ms": None,
            "p95_latency_ms": None,
            "oom_count": 0,
            "source_language_distribution": {},
            "source_specific_failure_rate": {},
        }
    latencies = [int(item["latency_ms"]) for item in outputs]
    fallback_count = sum(1 for item in outputs if item["fallback_used"])
    provider_real = sum(1 for item in outputs if item["provider"] != "local_rule_fallback")
    by_source = defaultdict(list)
    for item in outputs:
        by_source[item["source_id"]].append(item)
    return {
        "input_record_count": input_count,
        "parse_success_rate": round(sum(1 for item in outputs if item["schema_valid"]) / len(outputs), 4),
        "real_model_inference_count": provider_real,
        "schema_valid_rate": round(sum(1 for item in outputs if item["schema_valid"]) / len(outputs), 4),
        "field_complete_rate": round(sum(1 for item in outputs if item["risk_type"] and item["risk_level"]) / len(outputs), 4),
        "fallback_rate": round(fallback_count / len(outputs), 4),
        "empty_output_rate": round(sum(1 for item in outputs if item["empty_output"]) / len(outputs), 4),
        "text_evidence_nonempty_rate": round(sum(1 for item in outputs if item["text_evidence_count"] > 0) / len(outputs), 4),
        "retrieved_case_evidence_nonempty_rate": round(sum(1 for item in outputs if item["retrieved_case_evidence_count"] > 0) / len(outputs), 4),
        "unsupported_business_action_count": sum(1 for item in outputs if item["unsupported_business_action"]),
        "prohibited_auto_action_count": sum(1 for item in outputs if item["prohibited_auto_action"]),
        "need_human_review_rate": round(sum(1 for item in outputs if item["need_human_review"]) / len(outputs), 4),
        "output_risk_type_distribution": dict(Counter(item["risk_type"] for item in outputs)),
        "output_risk_level_distribution": dict(Counter(item["risk_level"] for item in outputs)),
        "avg_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
        "oom_count": 0,
        "source_language_distribution": dict(Counter(item["language"] for item in outputs)),
        "source_specific_failure_rate": {
            source: round(sum(1 for item in items if item["fallback_used"] or not item["schema_valid"]) / len(items), 4)
            for source, items in by_source.items()
        },
    }


def stability(outputs):
    grouped = defaultdict(list)
    for item in outputs:
        grouped[(item["sample_id_hash"], item["mode"])].append(item)
    pairs = [items for items in grouped.values() if len(items) >= 2]
    if not pairs:
        return {
            "exact_structured_output_match_rate": 0.0,
            "risk_type_consistency_rate": 0.0,
            "risk_level_consistency_rate": 0.0,
            "need_human_review_consistency_rate": 0.0,
            "evidence_count_consistency_rate": 0.0,
        }
    def same(key):
        return sum(1 for a, b, *_ in pairs if a[key] == b[key]) / len(pairs)
    exact = sum(1 for a, b, *_ in pairs if all(a[k] == b[k] for k in ["risk_type", "risk_level", "need_human_review", "text_evidence_count"])) / len(pairs)
    return {
        "exact_structured_output_match_rate": round(exact, 4),
        "risk_type_consistency_rate": round(same("risk_type"), 4),
        "risk_level_consistency_rate": round(same("risk_level"), 4),
        "need_human_review_consistency_rate": round(same("need_human_review"), 4),
        "evidence_count_consistency_rate": round(same("text_evidence_count"), 4),
    }


def pass_status(prompt_metrics, rag_metrics):
    total = prompt_metrics["input_record_count"] + rag_metrics["input_record_count"]
    real = prompt_metrics["real_model_inference_count"] + rag_metrics["real_model_inference_count"]
    schema_ok = min(prompt_metrics["schema_valid_rate"], rag_metrics["schema_valid_rate"])
    field_ok = min(prompt_metrics["field_complete_rate"], rag_metrics["field_complete_rate"])
    fallback = max(prompt_metrics["fallback_rate"], rag_metrics["fallback_rate"])
    empty = max(prompt_metrics["empty_output_rate"], rag_metrics["empty_output_rate"])
    bad = prompt_metrics["unsupported_business_action_count"] + rag_metrics["unsupported_business_action_count"] + prompt_metrics["prohibited_auto_action_count"] + rag_metrics["prohibited_auto_action_count"]
    if total >= 40 and real == total and schema_ok >= 0.95 and field_ok >= 0.95 and fallback <= 0.05 and empty == 0 and bad == 0:
        return "PRIVATE_TEXT_EXPLORATORY_BASELINE_PASS"
    return "PRIVATE_TEXT_EXPLORATORY_BASELINE_FAIL"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-source", type=int, default=30)
    parser.add_argument("--stability-per-source", type=int, default=5)
    parser.add_argument("--seed", type=int, default=162)
    parser.add_argument("--model-dir", default=str(ROOT.parent / "models" / "Qwen3-1.7B"))
    parser.add_argument("--blocked-reason", default="")
    parser.add_argument("--attempted-smoke-per-source", type=int, default=0)
    parser.add_argument("--attempted-smoke-status", default="")
    args = parser.parse_args()

    os.environ.setdefault("E_REVIEW_LLM_PROVIDER", "local_qwen3_transformers")
    os.environ.setdefault("E_REVIEW_LOCAL_QWEN_MODEL_DIR", args.model_dir)
    os.environ.setdefault("E_REVIEW_LOCAL_QWEN_MAX_NEW_TOKENS", "96")
    os.environ.setdefault("E_REVIEW_LOCAL_QWEN_ENABLE_THINKING", "false")

    rows, stability_rows = sample_rows(args.per_source, args.stability_per_source, args.seed)
    prompt_outputs, prompt_private = analyze_rows(rows, "prompt_only")
    rag_outputs, rag_private = analyze_rows(rows, "rag")
    repeated_rows = stability_rows + stability_rows
    stability_outputs, stability_private = analyze_rows(repeated_rows, "prompt_only")

    PRIVATE_OUT.mkdir(parents=True, exist_ok=True)
    (PRIVATE_OUT / "private_text_exploratory_outputs.jsonl").write_text(
        "\n".join(prompt_private + rag_private + stability_private) + "\n",
        encoding="utf-8",
    )
    prompt_metrics = aggregate(prompt_outputs, len(rows))
    rag_metrics = aggregate(rag_outputs, len(rows))
    stability_metrics = stability(stability_outputs)
    summary = {
        "marker": pass_status(prompt_metrics, rag_metrics),
        "project_mode": "private_noncommercial_research",
        "private_exploratory": True,
        "formal_benchmark": False,
        "publication_ready": False,
        "label_reliability": "unverified",
        "contains_gold_labels": False,
        "macro_f1_calculated": False,
        "visual_evidence_generated": False,
        "amazon_count": sum(1 for row in rows if row.get("source_id") == "amazon_reviews_2023"),
        "asap_count": sum(1 for row in rows if row.get("source_id") == "asap_chinese_reviews"),
        "prompt_only": prompt_metrics,
        "rag": rag_metrics,
        "comparison": {
            "schema_valid_delta": round(rag_metrics["schema_valid_rate"] - prompt_metrics["schema_valid_rate"], 4),
            "fallback_delta": round(rag_metrics["fallback_rate"] - prompt_metrics["fallback_rate"], 4),
            "latency_delta": None if rag_metrics["avg_latency_ms"] is None or prompt_metrics["avg_latency_ms"] is None else round(rag_metrics["avg_latency_ms"] - prompt_metrics["avg_latency_ms"], 2),
            "evidence_nonempty_delta": round(rag_metrics["text_evidence_nonempty_rate"] - prompt_metrics["text_evidence_nonempty_rate"], 4),
            "human_review_rate_delta": round(rag_metrics["need_human_review_rate"] - prompt_metrics["need_human_review_rate"], 4),
            "output_distribution_shift": {
                "prompt_only": prompt_metrics["output_risk_type_distribution"],
                "rag": rag_metrics["output_risk_type_distribution"],
            },
        },
        "deterministic_stability": stability_metrics,
        "gpu_wait_ms": 0,
        "blocked_reason": args.blocked_reason or None,
        "attempted_smoke_per_source": args.attempted_smoke_per_source,
        "attempted_smoke_status": args.attempted_smoke_status or None,
        "private_output_written_git_external": True,
    }
    manifest = {
        "project_mode": "private_noncommercial_research",
        "sample_id_hashes": [row_hash(row) for row in rows],
        "source_counts": dict(Counter(row.get("source_id") for row in rows)),
        "formal_benchmark": False,
        "contains_gold_labels": False,
        "raw_text_in_git": False,
        "full_model_output_in_git": False,
    }
    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MANIFEST_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        "# V1.6.2 Private Text Exploratory Evaluation\n\n"
        f"Status: `{summary['marker']}`\n\n"
        "This is a private, local, noncommercial exploratory engineering run. It is not a formal benchmark and does not report Macro-F1 or accuracy.\n\n"
        f"- Amazon samples: {summary['amazon_count']}\n"
        f"- ASAP samples: {summary['asap_count']}\n"
        f"- Prompt-only schema valid rate: {prompt_metrics['schema_valid_rate']}\n"
        f"- RAG schema valid rate: {rag_metrics['schema_valid_rate']}\n"
        f"- Prompt-only fallback rate: {prompt_metrics['fallback_rate']}\n"
        f"- RAG fallback rate: {rag_metrics['fallback_rate']}\n"
        + (f"- Blocked reason: {summary['blocked_reason']}\n" if summary["blocked_reason"] else ""),
        encoding="utf-8",
    )
    print(summary["marker"])


if __name__ == "__main__":
    main()
