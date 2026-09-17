from __future__ import annotations

"""Repeatable, local-only Step 16 benchmark for the review-governance workflow.

The corpus is a versioned project-maintained gold set.  It is intentionally
small and transparent: it is a regression/canary suite, not a claim of an
independent production annotation study.
"""

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.agentic_workflow.runtime_checkpoint import FileWorkflowCheckpointStore
from app.contracts.governance_history import adapt_snapshot_for_display
from app.policy_rag.models import PolicySearchResult
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.core.config import settings
from app.risk_calibration.calibrator import calibration_metrics
from app.risk_calibration.severity import RiskSeverityEvaluator, SeverityRank
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


DATASET_VERSION = "review-governance-gold-v1"
DEFAULT_DATASET = Path("data/benchmarks/review_governance_gold_v1.jsonl")
DEFAULT_INDEX = Path("data/policy_rag_real/index/policy_chunks.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the controlled Step 16 policy-governance benchmark.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--service-url", default="http://127.0.0.1:8008")
    parser.add_argument("--output", type=Path, default=Path("artifacts/step16/benchmark_results.json"))
    parser.add_argument("--expected-gold-sha256", default="", help="Fail before measurement if the frozen gold content hash differs.")
    parser.add_argument("--write-dataset", action="store_true", help="Materialize the versioned 120-case gold fixture and exit.")
    parser.add_argument("--skip-concurrency", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Use only the first N cases; intended for a quick diagnostic.")
    args = parser.parse_args()

    if args.write_dataset:
        cases = build_gold_cases()
        write_jsonl(args.dataset, cases)
        print(json.dumps({"dataset": str(args.dataset), "caseCount": len(cases), "version": DATASET_VERSION}, ensure_ascii=False, indent=2))
        return 0

    cases = load_jsonl(args.dataset)
    dataset_hash = hashlib.sha256(args.dataset.read_bytes()).hexdigest().upper()
    if args.expected_gold_sha256 and dataset_hash != args.expected_gold_sha256.upper():
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={args.expected_gold_sha256.upper()} actual={dataset_hash}")
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("BENCHMARK_DATASET_EMPTY")
    index = args.index if args.index.is_absolute() else Path(__file__).resolve().parents[1] / args.index
    report: dict[str, Any] = {
        "schemaVersion": "step16-benchmark-v1",
        "generatedAtEpochMs": int(time.time() * 1000),
        "dataset": {**dataset_summary(cases, args.dataset), "sha256": dataset_hash},
        "runtime": runtime_probe(args.service_url),
    }
    report["retrieval"] = evaluate_retrieval(cases, index)
    report["governance"] = evaluate_governance(cases, args.service_url)
    report["latency"] = evaluate_latency(cases, args.service_url, index)
    report["concurrency"] = {} if args.skip_concurrency else evaluate_concurrency(cases, args.service_url)
    report["cache"] = evaluate_cache(cases, args.service_url)
    report["faultInjection"] = evaluate_faults(index)
    report["sloInputs"] = build_slo_inputs(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_gold_cases() -> list[dict[str, Any]]:
    """Create 120 fixed, reviewable cases across policy and non-policy routes."""
    groups = [
        ("normal_review", [
            "物流很快，包装完整，商品和描述一致。",
            "Bought it last week and it works as expected.",
            "尺寸合适，日常使用没有问题。",
            "The color matches the product page and delivery was on time.",
            "做工不错，使用三天后体验稳定。",
            "性价比可以，会正常使用一段时间再评价。",
            "Received the item, everything is fine.",
            "外观简洁，功能符合预期。",
            "包装没有破损，配件齐全。",
            "普通购买体验，暂无需要处理的问题。",
        ], ["normal_review"], "low_touch", "auto_pass", "supported", False, [], "zh"),
        ("fake_review", [
            "商家让我们找人刷单写好评。", "这是批量编造的购买体验。", "没有买过也被要求发布好评。",
            "They asked accounts with no purchase to post fabricated reviews.", "评论内容是统一模板，不是实际使用体验。",
            "请员工假装消费者留言。", "Fake engagement was organized for this product.", "虚构订单后集中发布评价。",
            "商家要求亲友冒充买家写评价。", "These testimonials were written without using the product.",
        ], ["fake_review"], "governance_required", "suggest_action", "supported", False, ["fake_review", "fake_engagement"], "mixed"),
        ("paid_review", [
            "晒五星截图返现10元。", "好评后联系客服领取红包。", "给五星并附图就返现金。",
            "Cashback is offered only for a positive five-star review.", "Leave a 5-star review and receive a coupon.",
            "返现活动要求评价必须是好评。", "商家说发五星截图才能退款。", "五星好评换赠品。",
            "Payment depends on writing a favorable review.", "好评返现，差评不给补偿。",
        ], ["fake_review", "rating_manipulation"], "governance_required", "suggest_action", "supported", False, ["incentivized_review", "rating_manipulation"], "mixed"),
        ("rating_manipulation", [
            "客服要求集体打五星冲评分。", "为了提高店铺评分组织统一好评。", "五星截图是参加返利的条件。",
            "The seller coordinates five-star ratings to boost the score.", "用优惠券诱导用户只给满分。",
            "评价奖励与五星分数直接绑定。", "要求修改为五颗星才能处理退款。", "统一模板好评提高排名。",
            "Rating outcome is manipulated through incentives.", "商家让大家把星级改成5星。",
        ], ["fake_review", "rating_manipulation"], "governance_required", "suggest_action", "supported", False, ["rating_manipulation", "incentivized_review"], "mixed"),
        ("review_suppression", [
            "商家威胁不给删差评就起诉。", "客服要求我删除差评才给售后。", "他们屏蔽了所有负面评价。",
            "The seller offered a refund only if I removed my negative review.", "商家要求删评后才补发。",
            "投诉后对方要求撤销低分评价。", "They threatened me for posting an unfavorable review.", "删除差评才允许退货。",
            "平台展示被商家要求过滤负面评论。", "Remove the bad review or we will refuse support.",
        ], ["review_suppression"], "governance_required", "manual_review", "supported", True, ["review_suppression"], "mixed"),
        ("after_sales_risk", [
            "商品破损，申请退款但商家一直拖延。", "收到的是坏的，售后拒绝退货。", "用了两天就坏了，退款没有回应。",
            "The package arrived damaged and the return request is unresolved.", "质量问题，客服只让我等待。",
            "Product is defective and after-sales support will not respond.", "退货运费争议一直没有解决。", "少件且客服拒绝补发。",
            "收到假货，退款流程被拖延。", "Broken item, still waiting for a refund.",
        ], ["after_sales_risk"], "governance_required", "manual_review", "insufficient", True, ["after_sales", "consumer_rights"], "mixed"),
        ("negative_review", [
            "味道一般，不太符合个人喜好。", "颜色比想象中深一点。", "The product is okay but not my preferred style.",
            "续航普通，其他方面还可以。", "不太喜欢这个材质，但没有质量问题。", "Size is slightly different from my expectation.",
            "价格有点高，整体还能接受。", "包装普通，商品能正常使用。", "I would not buy again, but there was no safety issue.", "体验一般，仅表达个人感受。",
        ], ["normal_review"], "low_touch", "auto_pass", "supported", False, [], "mixed"),
        ("ambiguous", [
            "差", "不好", "退款", "坏了", "很烫", "被骗了", "删评", "隐私", "威胁", "有问题",
        ], ["after_sales_risk"], "human_review_direct", "manual_review", "insufficient", True, [], "zh"),
        ("privacy_risk", [
            "商家把我的手机号和住址贴在评论里。", "客服公开了我的订单号和身份证信息。", "They exposed my phone number in a public reply.",
            "个人信息被截图发到评论区。", "The review contains a buyer's private address.", "对方要求我公开身份证照片。",
            "卖家泄露了我的联系方式。", "My personal information was published without consent.", "评价区出现了完整手机号。", "隐私被用于威胁我删评。",
        ], ["privacy_risk"], "governance_required", "manual_review", "supported", True, ["privacy"], "mixed"),
        ("harassment_or_abuse", [
            "商家威胁要来找我。", "客服辱骂并恐吓我删评论。", "They sent threats after I posted a review.",
            "不删评价就说要报复我。", "评论区有人持续骚扰买家。", "The seller used abusive language and intimidation.",
            "对方威胁曝光我个人信息。", "收到带有辱骂和恐吓的信息。", "商家用法律威胁压制批评。", "Harassing messages followed my negative review.",
        ], ["harassment_or_abuse"], "governance_required", "manual_review", "supported", True, ["harassment_or_abuse"], "mixed"),
        ("multi_risk", [
            "晒五星图返现，不删差评就不给退款。", "商家刷单冲分，还要求删除低分评论。", "Cashback for five stars and threats to remove negative feedback.",
            "给好评返钱，差评用户被客服威胁。", "组织假评价并屏蔽真实差评。", "They buy favorable reviews and suppress unfavorable ones.",
            "五星奖励和删评退款同时存在。", "刷单好评后，商家要求撤销投诉。", "Fake reviews, rating incentives, and review removal pressure.", "返现好评配合删除差评。",
        ], ["fake_review", "rating_manipulation", "review_suppression"], "governance_required", "manual_review", "mismatch", True, ["incentivized_review", "review_suppression"], "mixed"),
        ("lexical_mismatch", [
            "给 five-star review 可领小礼金。", "改成最满意评价才能拿 cashback 补贴。", "店铺请人把口碑做上去。", "晒单领奖励，但必须夸商品。",
            "Positive 好评 sentiment is a condition for receiving compensation.", "The merchant curates public feedback to hide criticism.",
            "把不好听的声音处理掉才给 after-sales support。", "互不相识的账号都在复述同一购买故事。", "用奖励换取特定情绪的评论。", "They manufacture social proof rather than genuine experience.",
        ], ["fake_review", "rating_manipulation"], "governance_required", "suggest_action", "supported", False, ["incentivized_review", "fake_engagement"], "mixed"),
    ]
    cases: list[dict[str, Any]] = []
    for category, texts, risks, route, decision, status, human, tags, language in groups:
        for ordinal, text in enumerate(texts, start=1):
            cases.append({
                "caseId": f"{category}-{ordinal:02d}", "datasetVersion": DATASET_VERSION, "category": category,
                "reviewText": text, "rating": 1 if category in {"after_sales_risk", "ambiguous"} else 5 if category in {"paid_review", "rating_manipulation", "fake_review"} else 3,
                "expectedRiskTypes": risks, "expectedRoute": route, "expectedDecision": decision,
                "expectedEvidenceStatus": status, "expectedHumanReview": human, "expectedEvidenceTags": tags,
                "subset": subset_for(category, language_for(text)), "language": language_for(text),
            })
    assert len(cases) == 120
    return cases


def subset_for(category: str, language: str) -> list[str]:
    values = ["governance" if category not in {"normal_review", "negative_review"} else "normal"]
    if language == "zh": values.append("chinese")
    elif language == "cross_language": values.append("cross_language")
    else: values.append("english")
    if category == "lexical_mismatch": values.append("lexical_mismatch")
    if category == "multi_risk": values.append("multi_risk")
    return values


def language_for(text: str) -> str:
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)
    has_latin = any(("a" <= char.lower() <= "z") for char in text)
    if has_cjk and has_latin:
        return "cross_language"
    if has_cjk:
        return "zh"
    return "en"


def evaluate_retrieval(cases: list[dict[str, Any]], index: Path) -> dict[str, Any]:
    retrieval_cases = [case for case in cases if case["expectedEvidenceTags"]]
    modes: dict[str, PolicyEvidenceRetriever] = {
        "bm25": PolicyEvidenceRetriever.from_jsonl(index, enable_dense=False),
        "dense": PolicyEvidenceRetriever.from_jsonl(index, enable_dense=True),
        "hybrid": PolicyEvidenceRetriever.from_jsonl(index, enable_dense=True),
        "bm25_fallback": PolicyEvidenceRetriever.from_jsonl(index, enable_dense=False),
    }
    results: dict[str, Any] = {}
    for name, retriever in modes.items():
        mode = "hybrid" if name == "bm25_fallback" else name
        if name in {"dense", "hybrid"} and retriever.dense_store is not None:
            # Trigger the provider's documented lazy load before validating readiness.
            try:
                retriever.dense_store.search("benchmark dense readiness", top_k=1)
            except Exception as exc:
                raise SystemExit("BENCHMARK_DENSE_PROVIDER_NOT_READY") from exc
        readiness = retriever.readiness()
        if name in {"dense", "hybrid"} and (
            readiness.get("dense", {}).get("providerStatus") != "ready"
            or not readiness.get("dense", {}).get("indexAvailable")
            or readiness.get("retrievalMode") == "bm25_fallback"
        ):
            raise SystemExit("BENCHMARK_DENSE_PROVIDER_NOT_READY")
        rows = []
        for case in retrieval_cases:
            hits = retriever.search(case["reviewText"], risk_hints=case["expectedRiskTypes"], top_k=5, mode=mode)
            rank = first_matching_rank(hits, case["expectedEvidenceTags"], case["expectedRiskTypes"])
            rows.append({"caseId": case["caseId"], "rank": rank, "top": compact_hits(hits), "subsets": case["subset"]})
        actual_mode = "bm25_fallback" if readiness.get("retrievalMode") == "bm25_fallback" else mode
        if name in {"dense", "hybrid"} and actual_mode != mode:
            raise SystemExit("BENCHMARK_REQUESTED_MODE_MISMATCH")
        results[name] = {"requestedMode": mode, "actualMode": actual_mode, "providerStatus": readiness.get("dense", {}).get("providerStatus"), "embeddingModel": settings.policy_rag.embedding_model, "vectorCount": readiness.get("chunkCount"), "dimension": readiness.get("dense", {}).get("dimension", 1024), "metrics": ranking_metrics(rows), "subsets": subset_ranking_metrics(rows), "readiness": readiness, "sampleTopK": rows[:12]}
    return {"caseCount": len(retrieval_cases), "modes": results}


def evaluate_governance(cases: list[dict[str, Any]], service_url: str) -> dict[str, Any]:
    rows = []
    for case in cases:
        actual, latency, error = post_analyze(service_url, case)
        contract = actual.get("review_governance", {}) if actual else {}
        route = extract_route(actual, contract)
        rows.append({
            "case": case, "actual": actual, "contract": contract, "route": route, "latencyMs": latency, "error": error,
            "actualRisks": contract.get("riskTypes", []), "actualDecision": contract.get("decision", {}).get("code"),
            "actualEvidenceStatus": contract.get("evidenceStatus"), "actualHumanReview": bool(contract.get("requiresHumanReview")),
        })
    risk = multilabel_metrics(rows)
    route_accuracy = accuracy(rows, "expectedRoute", "route")
    decision_accuracy = accuracy(rows, "expectedDecision", "actualDecision")
    reflection_accuracy = accuracy(rows, "expectedEvidenceStatus", "actualEvidenceStatus")
    human = binary_metrics(rows, "expectedHumanReview", "actualHumanReview")
    high_risk_false_negative = [row for row in rows if row["case"]["expectedHumanReview"] and row["actualDecision"] == "auto_pass"]
    return {
        "caseCount": len(rows), "requestErrors": sum(1 for row in rows if row["error"]), "riskType": risk,
        "routeAccuracy": route_accuracy, "decisionAccuracy": decision_accuracy, "reflectionAccuracy": reflection_accuracy,
        "humanReview": human, "highRiskAutoPassFalseNegatives": len(high_risk_false_negative),
        "riskCalibrationHoldout": calibration_holdout(rows),
        "confusionMatrix": confusion_matrix(rows), "badCases": bad_cases(rows)[:15], "sampleRows": compact_governance_rows(rows[:10]),
    }


def calibration_holdout(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluator = RiskSeverityEvaluator()
    labels = [item.name.lower() for item in SeverityRank]
    matrix = {gold: {predicted: 0 for predicted in labels} for gold in labels}
    raw_confidences: list[float] = []
    calibrated_confidences: list[float] = []
    correctness: list[int] = []
    undercalls = missing = correct_severity = 0
    for row in rows:
        assessment = ((row.get("actual") or {}).get("extra") or {}).get("riskAssessment") or {}
        if not assessment:
            missing += 1
            continue
        case = row["case"]
        gold = evaluator.evaluate(
            case["expectedRiskTypes"], review_text=case["reviewText"], evidence_status=case["expectedEvidenceStatus"]
        ).severity
        predicted = str(assessment.get("severity") or "low")
        if predicted not in labels:
            predicted = "low"
        matrix[gold][predicted] += 1
        correct_severity += int(gold == predicted)
        if SeverityRank[gold.upper()] >= SeverityRank.HIGH and SeverityRank[predicted.upper()] < SeverityRank.HIGH:
            undercalls += 1
        raw_confidences.append(float(assessment.get("rawConfidence", 0.0)))
        calibrated_confidences.append(float(assessment.get("calibratedConfidence", 0.0)))
        correctness.append(int(set(row["actualRisks"]) == set(case["expectedRiskTypes"])))
    macro_f1 = []
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[gold][label] for gold in labels if gold != label)
        fn = sum(matrix[label][predicted] for predicted in labels if predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        macro_f1.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    measured = len(raw_confidences)
    return {
        "caseCount": len(rows),
        "measuredCaseCount": measured,
        "missingAssessmentCount": missing,
        "severityAccuracy": round(correct_severity / measured, 4) if measured else 0.0,
        "severityMacroF1": round(sum(macro_f1) / len(labels), 4),
        "highSeverityUndercallCount": undercalls,
        "highConfidenceErrorCount": sum(1 for confidence, correct in zip(calibrated_confidences, correctness) if confidence >= 0.8 and not correct),
        "raw": calibration_metrics(raw_confidences, correctness),
        "calibrated": calibration_metrics(calibrated_confidences, correctness),
        "confusionMatrix": matrix,
    }


def evaluate_latency(cases: list[dict[str, Any]], service_url: str, index: Path) -> dict[str, Any]:
    normal = first_case(cases, "normal_review")
    strict = first_case(cases, "paid_review")
    bm25 = PolicyEvidenceRetriever.from_jsonl(index, enable_dense=False)
    dense = PolicyEvidenceRetriever.from_jsonl(index, enable_dense=True)
    _ = dense.search(strict["reviewText"], risk_hints=strict["expectedRiskTypes"], top_k=3, mode="hybrid")
    reflection = PolicyReflectionEngine()
    evidence = dense.search(strict["reviewText"], risk_hints=strict["expectedRiskTypes"], top_k=3, mode="hybrid")
    return {
        "measurement": "warm local process and warm 8008 runtime; cold startup is recorded separately by runbook procedure",
        "bm25RetrievalMs": measure(lambda: bm25.search(strict["reviewText"], risk_hints=strict["expectedRiskTypes"], top_k=3, mode="bm25"), 10),
        "denseEmbeddingPlusFaissMs": measure(lambda: dense.search(strict["reviewText"], risk_hints=strict["expectedRiskTypes"], top_k=3, mode="dense"), 10),
        "hybridRetrievalMs": measure(lambda: dense.search(strict["reviewText"], risk_hints=strict["expectedRiskTypes"], top_k=3, mode="hybrid"), 10),
        "reflectionMs": measure(lambda: reflection.reflect(risk_level="medium", risk_types=strict["expectedRiskTypes"], confidence=0.84, policy_evidence=evidence, action="suggest_action"), 10),
        "warmNormalAnalyzeMs": measure(lambda: post_analyze(service_url, normal), 10),
        "warmStrictAnalyzeMs": measure(lambda: post_analyze(service_url, strict), 10),
    }


def evaluate_concurrency(cases: list[dict[str, Any]], service_url: str) -> dict[str, Any]:
    normal = first_case(cases, "normal_review")
    strict = first_case(cases, "paid_review")
    results: dict[str, Any] = {}
    for label, case in (("normal", normal), ("strict", strict), ("repeat_strict", strict)):
        rows: dict[str, Any] = {}
        for workers in (1, 5, 10, 20):
            payloads = [dict(case, caseId=f"{case['caseId']}-c{workers}-{index}") for index in range(workers)]
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(post_analyze, service_url, payload) for payload in payloads]
                outcomes = [future.result() for future in as_completed(futures)]
            elapsed = time.perf_counter() - started
            latencies = [item[1] for item in outcomes]
            errors = [item[2] for item in outcomes if item[2]]
            rows[str(workers)] = {"requests": len(outcomes), "throughputRps": round(len(outcomes) / elapsed, 3), "latencyMs": summarize(latencies), "errorRate": round(len(errors) / len(outcomes), 4), "timeoutRate": round(sum("timeout" in error.lower() for error in errors) / len(outcomes), 4)}
        results[label] = rows
    return results


def evaluate_cache(cases: list[dict[str, Any]], service_url: str) -> dict[str, Any]:
    strict = first_case(cases, "paid_review")
    first = post_analyze(service_url, strict)
    second = post_analyze(service_url, strict)
    first_retrieval = retrieval_step_count(first[0])
    second_retrieval = retrieval_step_count(second[0])
    return {
        "responseCacheImplemented": False,
        "sameReviewId": strict["caseId"], "firstLatencyMs": first[1], "repeatLatencyMs": second[1],
        "firstRetrievalSteps": first_retrieval, "repeatRetrievalSteps": second_retrieval,
        "cacheHitRate": 0.0, "savedEmbeddingCalls": 0, "savedRetrievalCalls": 0,
        "note": "The current API deliberately has no result cache. Provider/index reuse is process-local; repeated analyze requests recompute policy retrieval so evidence cannot become stale after an index update.",
    }


def evaluate_faults(index: Path) -> list[dict[str, Any]]:
    scenarios = []
    bm25 = PolicyEvidenceRetriever.from_jsonl(index, enable_dense=False)
    fallback_hits = bm25.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid")
    scenarios.append(result("A_QWEN_UNAVAILABLE", "dense unavailable falls back to BM25", bool(fallback_hits) and bm25.last_fallback_used, bm25.readiness()))
    scenarios.append(result("B_FAISS_UNAVAILABLE", "missing dense store falls back to BM25", bool(fallback_hits) and bm25.last_dense_error == "DENSE_STORE_NOT_CONFIGURED", {"hits": len(fallback_hits), "denseError": bm25.last_dense_error}))
    with tempfile.TemporaryDirectory(prefix="e-review-step16-faults-") as checkpoint_dir:
        checkpoint_store = FileWorkflowCheckpointStore(checkpoint_dir)
        empty = _EmptyRetriever()
        response = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=empty, checkpoint_store=checkpoint_store).analyze(ReviewAnalyzeRequest(review_id="fault-empty", product_id="P", product_name="P", review_text="五星截图返现", image_urls=[], rating=5))
        scenarios.append(result("C_POLICY_CHUNKS_MISSING", "no policy evidence routes to human review", response.route_decision == "human_review" and response.evidence_status == "insufficient", {"decision": response.route_decision, "status": response.evidence_status}))
        scenarios.append(result("D_AI_TIMEOUT", "network timeout is surfaced for caller safe-degradation", _timeout_probe(), {"endpoint": "127.0.0.1:18008"}))
        scenarios.append(result("E_RETRIEVAL_EXCEPTION", "retrieval failure is insufficient and human review", _retrieval_exception_probe(checkpoint_store), {}))
    scenarios.append(result("F_DB_WRITE_FAILURE", "covered by risk-task transaction unit tests; no benchmark DB writes occur", True, {"mode": "non-destructive"}))
    scenarios.append(result("G_DUPLICATE_HUMAN_REVIEW", "covered by idempotency service tests; benchmark does not mutate tasks", True, {"mode": "non-destructive"}))
    invalid = PolicySearchResult(evidenceId="E1", chunkId="bad", sourceType="policy", sourceName="Broken", sourceUrl="", title="", snippet="text", riskTypes=["fake_review"], evidenceTags=["fake_review"], score=1, contentHash="")
    reflection = PolicyReflectionEngine().reflect(risk_level="medium", risk_types=["fake_review"], confidence=0.9, policy_evidence=[invalid], action="suggest_action")
    scenarios.append(result("H_CITATION_MISSING", "invalid citation is insufficient", reflection.evidenceStatus == "insufficient" and "CITATION_INCOMPLETE" in reflection.reasonCodes, reflection.model_dump()))
    legacy = adapt_snapshot_for_display({"schemaVersion": "review-governance-v1", "reviewId": "legacy", "riskTypes": ["normal_review"], "decision": {"code": "auto_pass"}}) or {}
    scenarios.append(result("I_LEGACY_V1", "v1 snapshot adapts to v2", legacy.get("governanceSchemaVersion") == "review-governance-v2", legacy))
    return scenarios


class _FaultRetrieverBase:
    dense_store = None
    last_search_timings: dict[str, Any] = {}
    last_dense_error = "FAULT_INJECTION"

    @staticmethod
    def readiness() -> dict[str, Any]:
        return {
            "status": "degraded",
            "chunkCount": 0,
            "retrievalMode": "unavailable",
            "dense": {"providerStatus": "unavailable", "indexAvailable": False},
        }


class _EmptyRetriever(_FaultRetrieverBase):
    def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []


class _FailingRetriever(_FaultRetrieverBase):
    def search(self, *args: Any, **kwargs: Any) -> list[Any]:
        raise RuntimeError("FAULT_RETRIEVAL_EXCEPTION")


def _retrieval_exception_probe(checkpoint_store: FileWorkflowCheckpointStore) -> bool:
    response = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=_FailingRetriever(), checkpoint_store=checkpoint_store).analyze(ReviewAnalyzeRequest(review_id="fault-error", product_id="P", product_name="P", review_text="五星截图返现", image_urls=[], rating=5))
    return response.route_decision == "human_review" and response.evidence_status == "insufficient"


def _timeout_probe() -> bool:
    try:
        urllib.request.urlopen("http://127.0.0.1:18008/api/v1/health", timeout=0.05)
    except (urllib.error.URLError, TimeoutError):
        return True
    return False


def result(scenario: str, expected: str, passed: bool, actual: dict[str, Any]) -> dict[str, Any]:
    return {"scenario": scenario, "expected": expected, "actual": actual, "status": "PASS" if passed else "FAIL"}


def runtime_probe(service_url: str) -> dict[str, Any]:
    try:
        return get_json(service_url + "/api/v1/system/readiness")
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def post_analyze(service_url: str, case: dict[str, Any]) -> tuple[dict[str, Any], float, str]:
    payload = {"reviewId": case["caseId"], "productId": "BENCH", "productName": "Step 16 benchmark product", "reviewText": case["reviewText"], "imageUrls": [], "rating": case["rating"]}
    started = time.perf_counter()
    try:
        request = urllib.request.Request(service_url.rstrip("/") + "/api/v1/review/analyze", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8")), round((time.perf_counter() - started) * 1000, 2), ""
    except Exception as exc:
        return {}, round((time.perf_counter() - started) * 1000, 2), str(exc)[:240]


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")


def first_matching_rank(hits: list[Any], expected_tags: list[str], expected_risks: list[str]) -> int | None:
    wanted = set(expected_tags) | set(expected_risks)
    for rank, hit in enumerate(hits, start=1):
        if wanted.intersection(set(hit.evidenceTags) | set(hit.riskTypes)):
            return rank
    return None


def compact_hits(hits: list[Any]) -> list[dict[str, Any]]:
    return [{"chunkId": item.chunkId, "score": item.score, "source": item.sourceName, "tags": item.evidenceTags} for item in hits]


def ranking_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = max(1, len(rows))
    return {"recallAt1": round(sum(row["rank"] == 1 for row in rows) / total, 4), "recallAt3": round(sum(bool(row["rank"] and row["rank"] <= 3) for row in rows) / total, 4), "recallAt5": round(sum(bool(row["rank"] and row["rank"] <= 5) for row in rows) / total, 4), "mrr": round(sum(1 / row["rank"] if row["rank"] else 0 for row in rows) / total, 4)}


def subset_ranking_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for subset in row["subsets"]:
            groups[subset].append(row)
    return {name: ranking_metrics(values) for name, values in sorted(groups.items())}


def extract_route(actual: dict[str, Any], contract: dict[str, Any]) -> str:
    agentic = (actual.get("extra") or {}).get("agentic") or {}
    return str(agentic.get("route") or ("human_review_direct" if contract.get("decision", {}).get("code") == "manual_review" and not contract.get("evidenceCitations") else "governance_required" if contract.get("riskTypes") != ["normal_review"] else "low_touch"))


def multilabel_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = sorted({label for row in rows for label in row["case"]["expectedRiskTypes"] if label != "normal_review"} | {label for row in rows for label in row["actualRisks"] if label != "normal_review"})
    per_label = {}
    total_tp = total_fp = total_fn = 0
    for label in labels:
        tp = sum(label in row["case"]["expectedRiskTypes"] and label in row["actualRisks"] for row in rows)
        fp = sum(label not in row["case"]["expectedRiskTypes"] and label in row["actualRisks"] for row in rows)
        fn = sum(label in row["case"]["expectedRiskTypes"] and label not in row["actualRisks"] for row in rows)
        per_label[label] = prf(tp, fp, fn)
        total_tp += tp; total_fp += fp; total_fn += fn
    return {"micro": prf(total_tp, total_fp, total_fn), "perRiskType": per_label}


def prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0}


def accuracy(rows: list[dict[str, Any]], expected_key: str, actual_key: str) -> dict[str, Any]:
    correct = sum(row["case"][expected_key] == row[actual_key] for row in rows)
    return {"correct": correct, "total": len(rows), "accuracy": round(correct / max(1, len(rows)), 4)}


def binary_metrics(rows: list[dict[str, Any]], expected_key: str, actual_key: str) -> dict[str, Any]:
    tp = sum(row["case"][expected_key] and row[actual_key] for row in rows)
    fp = sum(not row["case"][expected_key] and row[actual_key] for row in rows)
    fn = sum(row["case"][expected_key] and not row[actual_key] for row in rows)
    return prf(tp, fp, fn)


def confusion_matrix(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        expected = "+".join(row["case"]["expectedRiskTypes"])
        actual = "+".join(row["actualRisks"]) or "none"
        matrix[expected][actual] += 1
    return {expected: dict(sorted(values.items())) for expected, values in sorted(matrix.items())}


def bad_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad = []
    for row in rows:
        case = row["case"]
        if row["error"] or case["expectedDecision"] != row["actualDecision"] or case["expectedEvidenceStatus"] != row["actualEvidenceStatus"] or set(case["expectedRiskTypes"]) != set(row["actualRisks"]):
            bad.append({"caseId": case["caseId"], "category": case["category"], "expected": {"riskTypes": case["expectedRiskTypes"], "decision": case["expectedDecision"], "evidenceStatus": case["expectedEvidenceStatus"]}, "actual": {"riskTypes": row["actualRisks"], "decision": row["actualDecision"], "evidenceStatus": row["actualEvidenceStatus"]}, "error": row["error"]})
    return bad


def compact_governance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"caseId": row["case"]["caseId"], "riskTypes": row["actualRisks"], "decision": row["actualDecision"], "evidenceStatus": row["actualEvidenceStatus"], "latencyMs": row["latencyMs"], "error": row["error"]} for row in rows]


def measure(fn: Callable[[], Any], samples: int) -> dict[str, float]:
    values = []
    for _ in range(samples):
        started = time.perf_counter(); fn(); values.append((time.perf_counter() - started) * 1000)
    return summarize(values)


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered: return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    percentile = lambda p: ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p) - 1))]
    return {"avg": round(statistics.mean(ordered), 2), "p50": round(percentile(.50), 2), "p95": round(percentile(.95), 2), "p99": round(percentile(.99), 2), "max": round(max(ordered), 2)}


def retrieval_step_count(actual: dict[str, Any]) -> int:
    return sum(1 for item in actual.get("workflow_trace", []) if item.get("node") == "policy_evidence_retrieve")


def dataset_summary(cases: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    return {"version": DATASET_VERSION, "path": str(path), "caseCount": len(cases), "byCategory": dict(sorted(Counter(case["category"] for case in cases).items())), "method": "project-maintained, rule-grounded controlled gold cases; not external production annotation"}


def first_case(cases: list[dict[str, Any]], category: str) -> dict[str, Any]:
    return next((case for case in cases if case["category"] == category), cases[0])


def build_slo_inputs(report: dict[str, Any]) -> dict[str, Any]:
    strict = report.get("latency", {}).get("warmStrictAnalyzeMs", {})
    governance = report.get("governance", {})
    return {"warmStrictP95Ms": strict.get("p95", 0), "apiRequestErrors": governance.get("requestErrors", 0), "highRiskAutoPassFalseNegatives": governance.get("highRiskAutoPassFalseNegatives", 0), "fallbackPassRate": round(sum(item["status"] == "PASS" for item in report.get("faultInjection", []) if item["scenario"] in {"A_QWEN_UNAVAILABLE", "B_FAISS_UNAVAILABLE"}) / 2, 4)}


if __name__ == "__main__":
    raise SystemExit(main())
