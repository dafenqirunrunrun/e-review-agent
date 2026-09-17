import argparse
import json
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = ROOT / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.agent_framework.graph import run_agent_graph  # noqa: E402
from app.schemas.review import ReviewAnalyzeRequest  # noqa: E402
from app.services.mock_analyzer import MockAnalyzer  # noqa: E402


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8-sig") as file:
        for line in file:
            line = line.strip()
            if line:
                yield json.loads(line)


def percent(hit: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(hit * 100.0 / total, 2)


def dominant_modality(response):
    value = response.dominant_modality or {}
    return value.get("dominant_modality") or value.get("dominant") or "text"


def review_required(response):
    value = response.dominant_modality or {}
    if value.get("review_required") is True:
        return True
    return response.conflict_score >= 0.35 or response.confidence < 0.55 or response.risk_level in ("medium", "high")


def risk_hit(response, expected_keywords):
    if not expected_keywords:
        return True
    risk_types = []
    if response.extra:
        risk_types = response.extra.get("risk_types") or []
    haystack = " ".join([
        response.risk_level or "",
        response.sentiment_label or "",
        " ".join(risk_types),
        " ".join(response.evidence or []),
        " ".join(response.text_evidence or []),
        " ".join(response.image_evidence or []),
    ])
    return any(keyword in haystack for keyword in expected_keywords)


def suggestion_action(response):
    suggestion = response.agent_suggestion
    if suggestion is None:
        return ""
    return suggestion.action or suggestion.priority or ""


def evaluate(input_path: Path):
    analyzer = MockAnalyzer()
    rows = list(load_jsonl(input_path))
    latencies = []
    results = []

    for item in rows:
        request = ReviewAnalyzeRequest(
            review_id=item["review_id"],
            product_id=str(item["product_id"]),
            product_name=item["product_name"],
            review_text=item["review_text"],
            rating=item.get("rating"),
            image_urls=item.get("image_urls") or [],
        )
        started = time.perf_counter()
        response = run_agent_graph(request, analyzer)
        latency_ms = int((time.perf_counter() - started) * 1000)
        latencies.append(latency_ms)
        expected_action = item.get("expected_action")
        action = suggestion_action(response)
        results.append({
            "review_id": item["review_id"],
            "sentiment_ok": response.sentiment_label == item.get("expected_sentiment"),
            "risk_ok": risk_hit(response, item.get("expected_risk_keywords") or []),
            "risk_level_ok": response.risk_level == item.get("expected_risk_level"),
            "conflict_ok": (response.conflict_score >= 0.35) == bool(item.get("expect_conflict")),
            "dominant_ok": dominant_modality(response) == item.get("expected_dominant_modality"),
            "review_required_ok": review_required(response) == bool(item.get("expect_review_required")),
            "suggestion_action_ok": not expected_action or action == expected_action,
            "fallback_used": bool(response.fallback_used),
            "case_retrieval_empty": len(response.similar_cases or []) == 0,
            "evidence_covered": len(response.evidence or []) > 0,
            "latency_ms": latency_ms,
        })

    total = len(results)
    summary = {
        "golden_sample_count": total,
        "sentiment_accuracy": percent(sum(1 for row in results if row["sentiment_ok"]), total),
        "risk_type_hit_rate": percent(sum(1 for row in results if row["risk_ok"]), total),
        "risk_level_accuracy": percent(sum(1 for row in results if row["risk_level_ok"]), total),
        "conflict_detection_accuracy": percent(sum(1 for row in results if row["conflict_ok"]), total),
        "dominant_modality_accuracy": percent(sum(1 for row in results if row["dominant_ok"]), total),
        "review_required_hit_rate": percent(sum(1 for row in results if row["review_required_ok"]), total),
        "suggestion_action_hit_rate": percent(sum(1 for row in results if row["suggestion_action_ok"]), total),
        "case_retrieval_non_empty_rate": percent(sum(1 for row in results if not row["case_retrieval_empty"]), total),
        "fallback_rate": percent(sum(1 for row in results if row["fallback_used"]), total),
        "average_latency_ms": round(statistics.mean(latencies), 2) if latencies else 0,
        "empty_case_retrieval_rate": percent(sum(1 for row in results if row["case_retrieval_empty"]), total),
        "evidence_coverage_rate": percent(sum(1 for row in results if row["evidence_covered"]), total),
        "result": "AGENT_QUALITY_CHECK_PASS",
    }
    return summary, results


def write_report(path: Path, summary, results):
    lines = [
        "# Agentic RAG Quality Evaluation Report",
        "",
        "This report evaluates the local E-Review Agent workflow against a golden review set. It is intended for graduation defense, product demonstration, and follow-up optimization. It does not claim production-grade model performance.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key, value in summary.items():
        if key != "result":
            lines.append(f"| {key} | {value} |")
    lines.extend([
        "",
        "## Case Results",
        "",
        "| review_id | sentiment | risk_type | risk_level | conflict | modality | suggestion | retrieval_non_empty | evidence | latency_ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |",
    ])
    for row in results:
        lines.append(
            f"| {row['review_id']} | {row['sentiment_ok']} | {row['risk_ok']} | {row['risk_level_ok']} | "
            f"{row['conflict_ok']} | {row['dominant_ok']} | {row['suggestion_action_ok']} | "
            f"{not row['case_retrieval_empty']} | {row['evidence_covered']} | {row['latency_ms']} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- The current demo uses local rules and local case memory by default.",
        "- Qdrant and external model calls are not required for this evaluation.",
        "- Metrics below 70% are treated as improvement warnings instead of release blockers.",
        "- Human operators remain responsible for final risk handling decisions.",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "docs" / "eval" / "golden_reviews.jsonl"))
    parser.add_argument("--report", default=str(ROOT / "docs" / "58_agent_rag_quality_eval_report.md"))
    parser.add_argument("--legacy-report", default=str(ROOT / "docs" / "55_agent_quality_eval_report.md"))
    args = parser.parse_args()

    summary, results = evaluate(Path(args.input))
    write_report(Path(args.report), summary, results)
    if args.legacy_report:
        write_report(Path(args.legacy_report), summary, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
