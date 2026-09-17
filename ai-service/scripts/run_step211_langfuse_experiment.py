from __future__ import annotations

"""Run the frozen governance corpus as an isolated Langfuse hosted experiment."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langfuse import Evaluation, Langfuse

from app.agentic_workflow.runtime_checkpoint import FileWorkflowCheckpointStore
from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.contracts.review_governance import attach_review_governance
from app.core.config import settings
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.schemas.review import ReviewAnalyzeRequest
from app.services.rule_agent import RuleAgentWorkflow
from app.services.mock_analyzer import MockAnalyzer
from app.llm.service import LlmReviewService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data/benchmarks/review_governance_gold_v1.jsonl"
DEFAULT_INDEX = ROOT / "data/policy_rag_real/index/policy_chunks.jsonl"
DEFAULT_MANIFEST = ROOT / "data/policy_rag_real/index/policy_manifest.json"
DEFAULT_BASELINE = ROOT / "artifacts/step18/gate_run3.json"
DEFAULT_OUTPUT = ROOT / "artifacts/langfuse/hosted_experiment_result.json"
DATASET_NAME = "e-review-governance-frozen-v1"
EXPERIMENT_NAME = "step21-1-hosted-frozen-governance"
FROZEN_GOLD_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
EVALUATOR_NAMES = (
    "risk_type_correct",
    "route_correct",
    "decision_correct",
    "reflection_correct",
    "citation_valid",
    "evidence_supported",
    "high_risk_auto_pass",
    "api_success",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def frozen_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _item_metadata(item: Any) -> dict[str, Any]:
    value = item.get("metadata") if isinstance(item, dict) else getattr(item, "metadata", None)
    return value if isinstance(value, dict) else {}


def _item_expected(item: Any) -> dict[str, Any]:
    value = item.get("expected_output") if isinstance(item, dict) else getattr(item, "expected_output", None)
    return value if isinstance(value, dict) else {}


def _item_input(item: Any) -> Any:
    return item.get("input") if isinstance(item, dict) else getattr(item, "input", None)


def validate_hosted_dataset(items: list[Any], cases: dict[str, dict[str, Any]], expected_sha: str) -> dict[str, int]:
    case_ids: list[str] = []
    for item in items:
        metadata = _item_metadata(item)
        case_id = str(metadata.get("caseId") or "")
        if not case_id or case_id not in cases:
            raise RuntimeError(f"HOSTED_DATASET_UNKNOWN_CASE:{case_id or 'missing'}")
        if str(metadata.get("goldSha256") or "").upper() != expected_sha:
            raise RuntimeError(f"HOSTED_DATASET_GOLD_SHA_MISMATCH:{case_id}")
        case = cases[case_id]
        expected = _item_expected(item)
        canonical = {
            "riskTypes": case["expectedRiskTypes"],
            "route": case["expectedRoute"],
            "decision": case["expectedDecision"],
            "reflection": case["expectedEvidenceStatus"],
        }
        if expected != canonical:
            raise RuntimeError(f"HOSTED_DATASET_EXPECTED_MISMATCH:{case_id}")
        if case["reviewText"] in json.dumps(_item_input(item), ensure_ascii=False):
            raise RuntimeError(f"HOSTED_DATASET_RAW_REVIEW_PRESENT:{case_id}")
        case_ids.append(case_id)
    duplicates = sum(count - 1 for count in Counter(case_ids).values() if count > 1)
    missing = len(set(cases) - set(case_ids))
    if duplicates or missing or len(items) != len(cases):
        raise RuntimeError(
            f"HOSTED_DATASET_CARDINALITY_MISMATCH:items={len(items)},cases={len(cases)},duplicates={duplicates},missing={missing}"
        )
    return {"itemCount": len(items), "duplicates": duplicates, "missing": missing}


def validate_dense_runtime(retriever: PolicyEvidenceRetriever, manifest: dict[str, Any]) -> dict[str, Any]:
    dense_store = retriever.dense_store
    if dense_store is None:
        raise RuntimeError("HOSTED_EXPERIMENT_DENSE_STORE_NOT_CONFIGURED")
    dense_store.search("hosted experiment dense readiness", top_k=1)
    readiness = retriever.readiness()
    dense = readiness.get("dense", {})
    manifest_dense = manifest.get("retrieval", {}).get("dense", {})
    vector_count = int(manifest_dense.get("vectorCount") or 0)
    dimension = int(manifest_dense.get("dimension") or 0)
    if (
        readiness.get("retrievalMode") != "hybrid"
        or dense.get("providerStatus") != "ready"
        or not dense.get("indexAvailable")
        or vector_count != len(retriever.chunks)
        or dimension <= 0
    ):
        raise RuntimeError("HOSTED_EXPERIMENT_HYBRID_NOT_READY")
    return {
        "requestedMode": "hybrid",
        "actualMode": readiness.get("retrievalMode"),
        "providerStatus": dense.get("providerStatus"),
        "embeddingModel": settings.policy_rag.embedding_model,
        "policyIndexVersion": manifest.get("indexHash", ""),
        "vectorCount": vector_count,
        "dimension": dimension,
    }


def _route(response: Any, contract: dict[str, Any]) -> str:
    agentic = (response.extra or {}).get("agentic") or {}
    if agentic.get("route"):
        return str(agentic["route"])
    decision = contract.get("decision", {}).get("code")
    if decision == "manual_review" and not contract.get("evidenceCitations"):
        return "human_review_direct"
    return "governance_required" if contract.get("riskTypes") != ["normal_review"] else "low_touch"


def _citation_valid(route: str, evidence_status: str, citations: list[dict[str, Any]]) -> bool:
    complete = all(
        citation.get("sourceName")
        and citation.get("sourceUrl")
        and citation.get("sectionPath")
        and citation.get("contentHash")
        for citation in citations
    )
    citation_required = route == "governance_required" and evidence_status == "supported"
    return bool(complete and (citations or not citation_required))


def build_task(
    cases: dict[str, dict[str, Any]],
    workflow: AgenticReviewWorkflow,
    llm_service: LlmReviewService,
    run_token: str,
) -> Callable[..., dict[str, Any]]:
    def task(*, item: Any, **_: Any) -> dict[str, Any]:
        case_id = str(_item_metadata(item).get("caseId") or "")
        case = cases[case_id]
        try:
            payload = ReviewAnalyzeRequest(
                review_id=f"step211-{run_token}-{case_id}",
                product_id="LANGFUSE-FROZEN",
                product_name="Step 21.1 isolated experiment fixture",
                review_text=case["reviewText"],
                image_urls=[],
                rating=case["rating"],
            )
            response = attach_review_governance(payload, llm_service.enhance(payload, workflow.analyze(payload)))
            contract = response.review_governance.model_dump() if response.review_governance else {}
            route = _route(response, contract)
            citations = contract.get("evidenceCitations") or []
            evidence_status = str(contract.get("evidenceStatus") or response.evidence_status or "insufficient")
            retrieval = (response.extra or {}).get("policyRetrieval") or {}
            return {
                "caseId": case_id,
                "riskTypes": contract.get("riskTypes") or response.risk_types,
                "route": route,
                "decision": contract.get("decision", {}).get("code"),
                "reflection": evidence_status,
                "requiresHumanReview": bool(contract.get("requiresHumanReview")),
                "riskLevel": contract.get("decision", {}).get("riskLevel") or response.risk_level,
                "citationCount": len(citations),
                "citationValid": int(_citation_valid(route, evidence_status, citations)),
                "evidenceSupported": int(evidence_status == "supported"),
                "requestedMode": retrieval.get("requestedMode", "not_required" if route == "low_touch" else "hybrid"),
                "actualMode": retrieval.get("actualMode", "not_required" if route == "low_touch" else "unknown"),
                "workflowNodes": [step.node for step in response.workflow_trace],
                "apiSuccess": 1,
            }
        except Exception as exc:
            return {
                "caseId": case_id,
                "riskTypes": [],
                "route": "error",
                "decision": "error",
                "reflection": "error",
                "requiresHumanReview": True,
                "citationCount": 0,
                "citationValid": 0,
                "evidenceSupported": 0,
                "requestedMode": "hybrid",
                "actualMode": "error",
                "workflowNodes": [],
                "apiSuccess": 0,
                "errorType": type(exc).__name__,
            }

    return task


def _equality_evaluation(name: str, actual: Any, expected: Any) -> Evaluation:
    matched = actual == expected
    return Evaluation(
        name=name,
        value=1 if matched else 0,
        comment="matched" if matched else f"expected={expected}; actual={actual}",
    )


def risk_type_correct(*, output: dict[str, Any], expected_output: dict[str, Any], **_: Any) -> Evaluation:
    return _equality_evaluation("risk_type_correct", sorted(output.get("riskTypes") or []), sorted(expected_output.get("riskTypes") or []))


def route_correct(*, output: dict[str, Any], expected_output: dict[str, Any], **_: Any) -> Evaluation:
    return _equality_evaluation("route_correct", output.get("route"), expected_output.get("route"))


def decision_correct(*, output: dict[str, Any], expected_output: dict[str, Any], **_: Any) -> Evaluation:
    return _equality_evaluation("decision_correct", output.get("decision"), expected_output.get("decision"))


def reflection_correct(*, output: dict[str, Any], expected_output: dict[str, Any], **_: Any) -> Evaluation:
    return _equality_evaluation("reflection_correct", output.get("reflection"), expected_output.get("reflection"))


def citation_valid(*, output: dict[str, Any], **_: Any) -> Evaluation:
    value = int(bool(output.get("citationValid")))
    return Evaluation(name="citation_valid", value=value, comment="citation metadata complete" if value else "citation metadata incomplete")


def evidence_supported(*, output: dict[str, Any], **_: Any) -> Evaluation:
    value = int(bool(output.get("evidenceSupported")))
    return Evaluation(name="evidence_supported", value=value, comment=f"actual reflection={output.get('reflection')}")


def make_high_risk_auto_pass(cases: dict[str, dict[str, Any]]) -> Callable[..., Evaluation]:
    def high_risk_auto_pass(*, output: dict[str, Any], metadata: dict[str, Any] | None = None, **_: Any) -> Evaluation:
        case = cases[str((metadata or {}).get("caseId") or "")]
        violation = bool(case["expectedHumanReview"] and output.get("decision") == "auto_pass")
        return Evaluation(name="high_risk_auto_pass", value=int(violation), comment="violation" if violation else "safe")

    return high_risk_auto_pass


def api_success(*, output: dict[str, Any], **_: Any) -> Evaluation:
    value = int(bool(output.get("apiSuccess")))
    return Evaluation(name="api_success", value=value, comment="workflow completed" if value else f"workflow failed: {output.get('errorType', 'unknown')}")


def evaluators(cases: dict[str, dict[str, Any]]) -> list[Callable[..., Evaluation]]:
    return [
        risk_type_correct,
        route_correct,
        decision_correct,
        reflection_correct,
        citation_valid,
        evidence_supported,
        make_high_risk_auto_pass(cases),
        api_success,
    ]


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def aggregate_results(result: Any, cases: dict[str, dict[str, Any]], dataset_count: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    score_counts = Counter()
    null_scores = 0
    traces_missing = 0
    for item_result in result.item_results:
        case_id = str(_item_metadata(item_result.item).get("caseId") or "")
        output = item_result.output if isinstance(item_result.output, dict) else {}
        evaluations = {evaluation.name: evaluation.value for evaluation in item_result.evaluations}
        score_counts.update(evaluations.keys())
        null_scores += sum(value is None for value in evaluations.values())
        traces_missing += int(not item_result.trace_id)
        rows.append({"caseId": case_id, "output": output, "scores": evaluations, "traceId": item_result.trace_id})

    labels = sorted(
        {label for case in cases.values() for label in case["expectedRiskTypes"] if label != "normal_review"}
        | {label for row in rows for label in row["output"].get("riskTypes", []) if label != "normal_review"}
    )
    tp = fp = fn = 0
    for label in labels:
        for row in rows:
            case = cases[row["caseId"]]
            expected = label in case["expectedRiskTypes"]
            actual = label in row["output"].get("riskTypes", [])
            tp += int(expected and actual)
            fp += int(not expected and actual)
            fn += int(expected and not actual)

    case_ids = [row["caseId"] for row in rows]
    duplicate_count = sum(count - 1 for count in Counter(case_ids).values() if count > 1)
    metrics = {
        "riskF1": _prf(tp, fp, fn),
        "routeAccuracy": _average_score(rows, "route_correct"),
        "decisionAccuracy": _average_score(rows, "decision_correct"),
        "reflectionAccuracy": _average_score(rows, "reflection_correct"),
        "riskTypeExactMatch": _average_score(rows, "risk_type_correct"),
        "citationValidRate": _average_score(rows, "citation_valid"),
        "evidenceSupportedRate": _average_score(rows, "evidence_supported"),
        "highRiskAutoPassCount": sum(int(row["scores"].get("high_risk_auto_pass") or 0) for row in rows),
        "apiErrors": sum(1 for row in rows if not row["output"].get("apiSuccess")),
    }
    integrity = {
        "datasetItems": dataset_count,
        "resultItems": len(rows),
        "skippedCases": dataset_count - len(rows),
        "duplicates": duplicate_count,
        "nullScores": null_scores,
        "missingTraceIds": traces_missing,
        "scoreDenominators": {name: score_counts.get(name, 0) for name in EVALUATOR_NAMES},
    }
    return {"metrics": metrics, "integrity": integrity, "items": rows}


def _average_score(rows: list[dict[str, Any]], name: str) -> float:
    values = [float(row["scores"][name]) for row in rows if name in row["scores"] and row["scores"][name] is not None]
    return round(sum(values) / len(values), 4) if values else 0.0


def compare_local_baseline(aggregate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    hosted = aggregate["metrics"]
    expected = {
        "riskF1": float(baseline["governance"]["riskType"]["micro"]["f1"]),
        "routeAccuracy": float(baseline["governance"]["routeAccuracy"]["accuracy"]),
        "decisionAccuracy": float(baseline["governance"]["decisionAccuracy"]["accuracy"]),
        "reflectionAccuracy": float(baseline["governance"]["reflectionAccuracy"]["accuracy"]),
        "highRiskAutoPassCount": int(baseline["governance"]["highRiskAutoPassFalseNegatives"]),
        "apiErrors": int(baseline["governance"]["requestErrors"]),
    }
    actual = {
        "riskF1": hosted["riskF1"]["f1"],
        "routeAccuracy": hosted["routeAccuracy"],
        "decisionAccuracy": hosted["decisionAccuracy"],
        "reflectionAccuracy": hosted["reflectionAccuracy"],
        "highRiskAutoPassCount": hosted["highRiskAutoPassCount"],
        "apiErrors": hosted["apiErrors"],
    }
    differences = {key: {"local": expected[key], "hosted": actual[key]} for key in expected if actual[key] != expected[key]}
    return {"source": str(DEFAULT_BASELINE.relative_to(ROOT)), "local": expected, "hosted": actual, "consistent": not differences, "differences": differences}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Step 21.1 frozen Langfuse hosted experiment.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dataset-name", default=DATASET_NAME)
    parser.add_argument("--limit", type=int, default=0, help="Diagnostic only; full gate requires all 120 hosted items.")
    args = parser.parse_args()

    dataset_path = args.dataset.resolve()
    actual_sha = frozen_sha(dataset_path)
    if actual_sha != FROZEN_GOLD_SHA:
        raise SystemExit(f"FROZEN_GOLD_HASH_MISMATCH expected={FROZEN_GOLD_SHA} actual={actual_sha}")
    case_rows = load_jsonl(dataset_path)
    cases = {row["caseId"]: row for row in case_rows}
    if len(case_rows) != 120 or len(cases) != 120:
        raise SystemExit(f"FROZEN_DATASET_CARDINALITY_MISMATCH rows={len(case_rows)} unique={len(cases)}")
    if not settings.langfuse_enabled or not settings.langfuse_host or not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        raise SystemExit("LANGFUSE_HOSTED_EXPERIMENT_NOT_CONFIGURED")

    client = Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        base_url=settings.langfuse_host,
        timeout=10,
        environment=settings.langfuse_environment,
        release=settings.langfuse_release or None,
    )
    if not client.auth_check():
        raise SystemExit("LANGFUSE_AUTH_CHECK_FAILED")
    dataset = client.get_dataset(args.dataset_name)
    validation = validate_hosted_dataset(dataset.items, cases, actual_sha)

    retriever = PolicyEvidenceRetriever.from_jsonl(args.index.resolve(), enable_dense=True)
    runtime = validate_dense_runtime(retriever, load_json(args.manifest.resolve()))
    run_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = f"{EXPERIMENT_NAME}-{run_token}"
    selected_items = dataset.items[: args.limit] if args.limit else dataset.items
    selected_case_ids = {str(_item_metadata(item).get("caseId")) for item in selected_items}
    selected_cases = {case_id: cases[case_id] for case_id in selected_case_ids}

    previous_langfuse_enabled = os.environ.get("LANGFUSE_ENABLED")
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="e-review-step211-checkpoints-") as checkpoint_dir:
        analyzer = MockAnalyzer()
        workflow = AgenticReviewWorkflow(
            analyzer=analyzer,
            policy_retriever=retriever,
            checkpoint_store=FileWorkflowCheckpointStore(checkpoint_dir),
        )
        llm_service = LlmReviewService(RuleAgentWorkflow(analyzer=analyzer))
        # The experiment runner owns the item trace. Disable the request sidecar here
        # to avoid detached duplicate traces while keeping business behavior unchanged.
        os.environ["LANGFUSE_ENABLED"] = "false"
        try:
            result = client.run_experiment(
                name=EXPERIMENT_NAME,
                run_name=run_name,
                description="Deterministic mirror of the unchanged 120-case frozen E-Review governance benchmark.",
                data=selected_items,
                task=build_task(cases, workflow, llm_service, run_token),
                evaluators=evaluators(cases),
                max_concurrency=1,
                metadata={
                    "goldSha256": actual_sha,
                    "datasetName": args.dataset_name,
                    "workflowVersion": "review-agentic-v1",
                    "policyIndexVersion": runtime["policyIndexVersion"],
                    "requestedMode": "hybrid",
                    "runtimeIsolation": "temporary_checkpoint_no_business_persistence",
                },
            )
        finally:
            if previous_langfuse_enabled is None:
                os.environ.pop("LANGFUSE_ENABLED", None)
            else:
                os.environ["LANGFUSE_ENABLED"] = previous_langfuse_enabled

    aggregate = aggregate_results(result, cases, len(selected_items))
    baseline = load_json(args.baseline.resolve())
    baseline_consistency = compare_local_baseline(aggregate, baseline) if not args.limit else {"consistent": None, "reason": "diagnostic subset"}
    integrity = aggregate["integrity"]
    expected_count = len(selected_items)
    integrity_pass = (
        integrity["resultItems"] == expected_count
        and integrity["skippedCases"] == 0
        and integrity["duplicates"] == 0
        and integrity["nullScores"] == 0
        and integrity["missingTraceIds"] == 0
        and all(value == expected_count for value in integrity["scoreDenominators"].values())
    )
    gate_pass = bool(integrity_pass and aggregate["metrics"]["apiErrors"] == 0 and (args.limit or baseline_consistency["consistent"]))
    report = {
        "schemaVersion": "step21-1-hosted-experiment-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "experimentName": EXPERIMENT_NAME,
        "runName": result.run_name,
        "datasetName": args.dataset_name,
        "datasetRunId": result.dataset_run_id,
        "datasetRunUrl": result.dataset_run_url,
        "goldSha256": actual_sha,
        "hostedDataset": validation,
        "runtime": runtime,
        "runtimeIsolation": {
            "checkpoint": "temporary directory removed after run",
            "humanReviewTaskWrites": 0,
            "businessRecordWrites": 0,
            "requestSidecar": "disabled; experiment runner owns item trace",
        },
        "evaluatorList": list(EVALUATOR_NAMES),
        "durationSeconds": round(time.perf_counter() - started, 2),
        "integrity": integrity,
        "metrics": aggregate["metrics"],
        "localBaselineConsistency": baseline_consistency,
        "gate": "PASS" if gate_pass else "FAIL",
        "items": aggregate["items"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in report.items() if key != "items"}, ensure_ascii=False, indent=2))
    client.flush()
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
