from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agentic_workflow.workflow import AgenticReviewWorkflow, IntentRouterAgent
from app.contracts.review_governance import attach_review_governance
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer
try:
    from scripts.analyze_step17_false_negatives import FROZEN_GOLD_SHA256
    from scripts.run_step16_benchmark import accuracy, binary_metrics, load_jsonl, multilabel_metrics
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    from analyze_step17_false_negatives import FROZEN_GOLD_SHA256
    from run_step16_benchmark import accuracy, binary_metrics, load_jsonl, multilabel_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Step 17 router/safety-gate ablation on frozen gold.")
    parser.add_argument("--dataset", type=Path, default=Path("data/benchmarks/review_governance_gold_v1.jsonl"))
    parser.add_argument("--index", type=Path, default=Path("data/policy_rag_real/index/policy_chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/step17/ablation_results.json"))
    args = parser.parse_args()
    digest = hashlib.sha256(args.dataset.read_bytes()).hexdigest().upper()
    if digest != FROZEN_GOLD_SHA256:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_GOLD_SHA256} actual={digest}")
    cases = load_jsonl(args.dataset)
    index = args.index if args.index.is_absolute() else Path(__file__).resolve().parents[1] / args.index
    retriever = PolicyEvidenceRetriever.from_jsonl(index, enable_dense=False)
    variants = {
        "baseline": (False, False),
        "router_enhancements_only": (True, False),
        "safety_gate_only": (False, True),
        "router_plus_safety_gate": (True, True),
    }
    report = {"schemaVersion": "step17-ablation-v1", "goldSha256": digest, "caseCount": len(cases), "variants": {}}
    for name, (enhancements, gate) in variants.items():
        report["variants"][name] = evaluate(cases, retriever, enhancements, gate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def evaluate(cases: list[dict], retriever: PolicyEvidenceRetriever, enhancements: bool, gate: bool) -> dict:
    workflow = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(), policy_retriever=retriever,
        intent_router=IntentRouterAgent(rule_enhancements_enabled=enhancements, safety_gate_enabled=gate),
    )
    rows = []
    for case in cases:
        payload = ReviewAnalyzeRequest(
            review_id=case["caseId"], product_id="BENCH", product_name="Step 17 benchmark",
            review_text=case["reviewText"], image_urls=[], rating=case["rating"],
        )
        response = attach_review_governance(payload, workflow.analyze(payload))
        governance = response.review_governance.model_dump()
        route = ((response.extra or {}).get("agentic") or {}).get("route", "unknown")
        rows.append({
            "case": case, "route": route, "actualRisks": governance["riskTypes"],
            "actualDecision": governance["decision"]["code"], "actualEvidenceStatus": governance["evidenceStatus"],
            "actualHumanReview": governance["requiresHumanReview"],
        })
    high_risk = [row for row in rows if row["case"]["expectedHumanReview"]]
    normal = [row for row in rows if row["case"]["expectedRiskTypes"] == ["normal_review"]]
    return {
        "riskType": multilabel_metrics(rows),
        "routeAccuracy": accuracy(rows, "expectedRoute", "route"),
        "decisionAccuracy": accuracy(rows, "expectedDecision", "actualDecision"),
        "reflectionAccuracy": accuracy(rows, "expectedEvidenceStatus", "actualEvidenceStatus"),
        "humanReview": binary_metrics(rows, "expectedHumanReview", "actualHumanReview"),
        "highRiskAutoPassCount": sum(row["actualDecision"] == "auto_pass" for row in high_risk),
        "highRiskRecall": round(sum(row["actualDecision"] != "auto_pass" for row in high_risk) / len(high_risk), 4),
        "strictRouteRate": round(sum(row["route"] != "low_touch" for row in rows) / len(rows), 4),
        "normalStrictFalsePositiveRate": round(sum(row["route"] != "low_touch" for row in normal) / len(normal), 4),
        "normalAutoPassRate": round(sum(row["actualDecision"] == "auto_pass" for row in normal) / len(normal), 4),
    }


if __name__ == "__main__":
    raise SystemExit(main())
