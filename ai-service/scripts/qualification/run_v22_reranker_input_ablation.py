from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
QUALIFICATION = SCRIPTS / "qualification"
for item in (AI_ROOT, SCRIPTS, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.agent_rag.metrics import macro_average, score_query  # noqa: E402
from app.agent_rag.reranker import GovernedReranker, RerankerConfig  # noqa: E402
from run_v22_answerable_ranking_gate import build_candidate_pool_manifest  # noqa: E402
from run_v22_real_reranker_benchmark import apply_asset_manifest, benchmark_payload, build_manifest  # noqa: E402


OUT = ROOT / "artifacts" / "real-model-chain"
DOCS = ROOT / "docs" / "real-model-chain"
EVALUATION_TIME_UTC = "2026-07-22T00:00:00Z"
SOURCE_COMMIT = "7c592a6f"
SELECTED = {"candidateK": 8, "maximumFinalK": 5, "batchSize": 8, "maxLength": 384}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    args = parser.parse_args()
    if args.asset_manifest:
        os.environ["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
        apply_asset_manifest(Path(args.asset_manifest))
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    payload = benchmark_payload()
    manifest = build_manifest(payload)
    _candidate_manifest, rows_by_case = build_candidate_pool_manifest(payload, manifest)
    cases = [case for case in payload["cases"] if case["relevantChunkIds"] and set(case["relevantChunkIds"]) & {item.chunkId for item in rows_by_case[case["caseId"]]}]
    det_summary = deterministic_summary(cases, rows_by_case)
    model = load_reranker()
    variants = [
        ("A_CURRENT_CONTENT_ONLY", passage_content_only),
        ("C_TITLE_CONTENT", passage_title_content),
        ("E_TITLE_SECTION_CONTENT", passage_title_section_content),
        ("F_SAFE_METADATA_CONTENT", passage_safe_metadata_content),
    ]
    results = []
    for name, builder in variants:
        results.append(evaluate_variant(model, name, cases, rows_by_case, builder, max_length=SELECTED["maxLength"], batch_size=SELECTED["batchSize"], use_fp16=True))
    length_results = []
    best = best_variant(results)
    for length in (384, 512):
        length_results.append(evaluate_variant(model, f"{best['variant']}_LEN_{length}", cases, rows_by_case, builder_for(best["variant"]), max_length=length, batch_size=1, use_fp16=True))
    batch_results = []
    for batch in (1, 2, 4):
        batch_results.append(evaluate_variant(model, f"{best['variant']}_BATCH_{batch}", cases, rows_by_case, builder_for(best["variant"]), max_length=SELECTED["maxLength"], batch_size=batch, use_fp16=True))
    root = root_cause_decision(det_summary, results, length_results, batch_results)
    summary = {
        "schemaVersion": "agent-rag-v22-reranker-input-ablation-summary-v1",
        "sourceCommit": SOURCE_COMMIT,
        "benchmarkHash": manifest["benchmarkHash"],
        "knowledgeHash": manifest["knowledgeHash"],
        "diagnosticCaseCount": len(cases),
        "deterministicBaseline": det_summary,
        "stage1PassageRepresentation": results,
        "stage3MaxLength": length_results,
        "stage4BatchDeterminism": batch_results,
        "bestDiagnosticRepresentation": best["variant"],
        "rootCauseDecision": root["primaryRootCause"],
        "decision": root["decision"],
    }
    write_json(OUT / "v22-reranker-input-ablation-summary.json", summary)
    write_json(OUT / "v22-reranker-root-cause-decision.json", root)
    write_markdown(DOCS / "V22_PHASE_88_RERANKER_ROOT_CAUSE_DECISION.md", render_root(root, summary))
    print(root["decision"])
    return 0


def load_reranker() -> Any:
    from FlagEmbedding import FlagReranker

    path = os.getenv("RAG_RERANKER_MODEL_PATH", "")
    if not path:
        raise SystemExit("RAG_RERANKER_MODEL_PATH_REQUIRED")
    return FlagReranker(path, use_fp16=True)


def evaluate_variant(model: Any, variant: str, cases: list[dict[str, Any]], rows_by_case: dict[str, list[Any]], passage_builder: Callable[[Any], str], *, max_length: int, batch_size: int, use_fp16: bool) -> dict[str, Any]:
    rows = []
    latencies = []
    for case in cases:
        base = rows_by_case[case["caseId"]][: SELECTED["candidateK"]]
        pairs = [(case["query"], passage_builder(item)) for item in base]
        started = time.perf_counter()
        scores = model.compute_score(pairs, batch_size=batch_size, max_length=max_length, normalize=True)
        latencies.append(round((time.perf_counter() - started) * 1000, 3))
        score_values = [float(value) for value in scores]
        ranked = sorted(zip(score_values, base, strict=True), key=lambda value: (-value[0], value[1].rawRank or 9999, value[1].chunkId))
        ids = [item.chunkId for _score, item in ranked]
        rows.append(row_metrics(case, base, ids, score_values))
    metrics = aggregate(rows)
    return {
        "variant": variant,
        "useFp16": use_fp16,
        "maxLength": max_length,
        "batchSize": batch_size,
        **metrics,
        "latency": {"p50": percentile(latencies, 0.5), "p95": percentile(latencies, 0.95)},
        "caseResultHash": stable_case_hash(rows),
    }


def deterministic_summary(cases: list[dict[str, Any]], rows_by_case: dict[str, list[Any]]) -> dict[str, Any]:
    det = GovernedReranker(RerankerConfig(requested_type="deterministic", candidate_k=SELECTED["candidateK"], final_k=SELECTED["maximumFinalK"]))
    rows = []
    for case in cases:
        base = rows_by_case[case["caseId"]][: SELECTED["candidateK"]]
        result = det.rerank(case["query"], base, top_k=SELECTED["candidateK"], tenant_id=case["tenantId"], request_id=case["caseId"], evaluation_time_utc=EVALUATION_TIME_UTC)
        rows.append(row_metrics(case, base, [item.chunkId for item in result.candidates], result.scores))
    return aggregate(rows)


def row_metrics(case: dict[str, Any], base: list[Any], ranked_ids: list[str], scores: list[float]) -> dict[str, Any]:
    relevant = set(case["relevantChunkIds"])
    base_ids = [item.chunkId for item in base]
    base_best = best_rank(base_ids, relevant)
    new_best = best_rank(ranked_ids, relevant)
    group = ranking_group(base_best, new_best)
    return {
        "caseId": case["caseId"],
        "category": normalize_category(case["retrievalChallengeType"]),
        "metrics": score_query(
            retrieved_chunk_ids=ranked_ids[: SELECTED["maximumFinalK"]],
            relevant_chunk_ids=relevant,
            forbidden_chunk_ids=set(case["forbiddenChunkIds"]),
            relevance_grades=case["relevanceGrades"],
        ),
        "baseBestRank": base_best,
        "newBestRank": new_best,
        "rankingGroup": group,
        "top5RelevantBefore": any(chunk_id in relevant for chunk_id in base_ids[: SELECTED["maximumFinalK"]]),
        "top5RelevantAfter": any(chunk_id in relevant for chunk_id in ranked_ids[: SELECTED["maximumFinalK"]]),
        "scoreCount": len(scores),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    subsets = {}
    for category in ["overall", "lexical", "semantic", "mixed", "temporal", "tenant-isolation"]:
        selected = rows if category == "overall" else [row for row in rows if row["category"] == category]
        subsets[category] = {"caseCount": len(selected), **aggregate_mode([row["metrics"] for row in selected])}
    groups = Counter(row["rankingGroup"] for row in rows)
    return {
        "caseCount": len(rows),
        "subsets": subsets,
        "improvedCases": groups["IMPROVED"],
        "regressedCases": groups["SLIGHTLY_REGRESSED"] + groups["SEVERELY_REGRESSED"],
        "severelyRegressedCases": groups["SEVERELY_REGRESSED"],
        "top5Retention": round(sum(1 for row in rows if row["top5RelevantBefore"] and row["top5RelevantAfter"]) / max(1, sum(1 for row in rows if row["top5RelevantBefore"])), 6),
        "relevantPromotionRate": round(groups["IMPROVED"] / max(1, len(rows)), 6),
        "relevantDemotionRate": round((groups["SLIGHTLY_REGRESSED"] + groups["SEVERELY_REGRESSED"]) / max(1, len(rows)), 6),
    }


def root_cause_decision(det: dict[str, Any], variants: list[dict[str, Any]], lengths: list[dict[str, Any]], batches: list[dict[str, Any]]) -> dict[str, Any]:
    current = next(item for item in variants if item["variant"] == "A_CURRENT_CONTENT_ONLY")
    best = best_variant(variants)
    deterministic_overall = det["subsets"]["overall"]
    improved_by_representation = best["subsets"]["overall"]["ndcgAt5"] > current["subsets"]["overall"]["ndcgAt5"] + 0.03
    still_below_det = best["subsets"]["overall"]["ndcgAt5"] + 0.05 < deterministic_overall["ndcgAt5"]
    batch_hashes = {item["caseResultHash"] for item in batches}
    batch_stable = len(batch_hashes) == 1
    if improved_by_representation and not still_below_det:
        primary = "INPUT_REPRESENTATION_MISMATCH"
        decision = "RERANKER_RECOVERY_EXPERIMENT_JUSTIFIED"
        recoverable = True
        fix = "Use a single safe passage representation that includes title/section with content, then verify on unseen holdout."
    elif improved_by_representation and still_below_det:
        primary = "MULTIPLE_CONTRIBUTING_FACTORS"
        decision = "ROOT_CAUSE_UNRESOLVED"
        recoverable = False
        fix = ""
    else:
        primary = "UNFAIR_BASELINE_INFORMATION_ADVANTAGE" if still_below_det else "MODEL_DOMAIN_MISMATCH"
        decision = "REAL_RERANKER_MODEL_TASK_MISMATCH" if still_below_det and batch_stable else "ROOT_CAUSE_UNRESOLVED"
        recoverable = False
        fix = ""
    return {
        "schemaVersion": "agent-rag-v22-reranker-root-cause-decision-v1",
        "sourceCommit": SOURCE_COMMIT,
        "primaryRootCause": primary,
        "secondaryCauses": ["PASSAGE_REPRESENTATION_INCOMPLETE", "UNFAIR_BASELINE_INFORMATION_ADVANTAGE"],
        "recoverable": recoverable,
        "singleExplainableFix": fix,
        "newHoldoutRequired": True,
        "batchDeterministic": batch_stable,
        "currentRepresentation": metric_slice(current),
        "bestDiagnosticRepresentation": metric_slice(best),
        "deterministicBaseline": metric_slice(det),
        "decision": decision,
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED",
            "REAL_LLM_QUALITY_VERIFIED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }


def render_root(root: dict[str, Any], summary: dict[str, Any]) -> str:
    current = root["currentRepresentation"]
    best = root["bestDiagnosticRepresentation"]
    det = root["deterministicBaseline"]
    return f"""# V2.2 Phase 8.8 Reranker Root Cause Decision

## Decision

- Decision: `{root['decision']}`
- Primary root cause: `{root['primaryRootCause']}`
- Recoverable: `{root['recoverable']}`
- New holdout required: `{root['newHoldoutRequired']}`
- Batch deterministic: `{root['batchDeterministic']}`

## Metrics

| Path | overall nDCG@5 | overall MRR | semantic nDCG@5 | semantic MRR | severe regressions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current real representation | {current['overallNdcgAt5']} | {current['overallMrr']} | {current['semanticNdcgAt5']} | {current['semanticMrr']} | {current['severelyRegressedCases']} |
| Best diagnostic representation | {best['overallNdcgAt5']} | {best['overallMrr']} | {best['semanticNdcgAt5']} | {best['semanticMrr']} | {best['severelyRegressedCases']} |
| Deterministic baseline | {det['overallNdcgAt5']} | {det['overallMrr']} | {det['semanticNdcgAt5']} | {det['semanticMrr']} | {det['severelyRegressedCases']} |

## Boundary

The consumed 74-case diagnostic set cannot verify the model. A recovery experiment, if justified, requires a new unseen answerable holdout before `MODEL_RERANKER_VERIFIED` can be considered.
"""


def passage_content_only(item: Any) -> str:
    return str((item.row or {}).get("content") or (item.row or {}).get("text") or "")


def passage_title_content(item: Any) -> str:
    row = item.row or {}
    return "\n".join(part for part in [str(row.get("title") or ""), passage_content_only(item)] if part)


def passage_title_section_content(item: Any) -> str:
    row = item.row or {}
    return "\n".join(part for part in [str(row.get("title") or ""), str(row.get("section_title") or row.get("sectionTitle") or ""), passage_content_only(item)] if part)


def passage_safe_metadata_content(item: Any) -> str:
    row = item.row or {}
    safe = [
        f"sourceType: {row.get('source_type') or row.get('sourceType') or ''}",
        f"scope: {row.get('visibility') or ''}",
        f"title: {row.get('title') or ''}",
        f"section: {row.get('section_title') or row.get('sectionTitle') or ''}",
        passage_content_only(item),
    ]
    return "\n".join(part for part in safe if part and not part.endswith(": "))


def builder_for(name: str) -> Callable[[Any], str]:
    if name.startswith("C_TITLE_CONTENT"):
        return passage_title_content
    if name.startswith("E_TITLE_SECTION_CONTENT"):
        return passage_title_section_content
    if name.startswith("F_SAFE_METADATA_CONTENT"):
        return passage_safe_metadata_content
    return passage_content_only


def best_variant(values: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(values, key=lambda item: (item["subsets"]["semantic"]["ndcgAt5"], item["subsets"]["overall"]["ndcgAt5"], -item["severelyRegressedCases"]), reverse=True)[0]


def aggregate_mode(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {"hitRateAt5": 0.0, "recallAt5": 0.0, "mrr": 0.0, "ndcgAt5": 0.0}
    return macro_average(rows, ["hitRateAt5", "recallAt5", "mrr", "ndcgAt5"])


def metric_slice(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "overallNdcgAt5": item["subsets"]["overall"]["ndcgAt5"],
        "overallMrr": item["subsets"]["overall"]["mrr"],
        "semanticNdcgAt5": item["subsets"]["semantic"]["ndcgAt5"],
        "semanticMrr": item["subsets"]["semantic"]["mrr"],
        "severelyRegressedCases": item.get("severelyRegressedCases", 0),
    }


def best_rank(ids: list[str], relevant: set[str]) -> int:
    ranks = [ids.index(chunk_id) + 1 for chunk_id in relevant if chunk_id in ids]
    return min(ranks) if ranks else 0


def ranking_group(original_best: int, new_best: int) -> str:
    if original_best and new_best and new_best < original_best:
        return "IMPROVED"
    if original_best == new_best:
        return "UNCHANGED"
    if new_best == 0 or (original_best <= 5 and new_best > 5) or (new_best - original_best >= 3):
        return "SEVERELY_REGRESSED"
    return "SLIGHTLY_REGRESSED"


def normalize_category(value: str) -> str:
    return "no-answer" if value == "negative/no-answer" else value


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[max(0, min(index, len(ordered) - 1))], 3)


def stable_case_hash(rows: list[dict[str, Any]]) -> str:
    payload = [{"caseId": row["caseId"], "group": row["rankingGroup"], "best": row["newBestRank"]} for row in rows]
    return json_hash(payload)


def json_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
