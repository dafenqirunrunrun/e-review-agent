from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase, RetrievalHit, RetrievalRunCase
from scripts.build_step242a_rag_quality_v2 import content_root_hash, load_jsonl, sha256_file, write_json


DEFAULT_DATASET = ROOT / "data" / "benchmarks" / "rag_quality_v2" / "dataset_candidate.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "benchmarks" / "rag_quality_v2" / "manifest.json"
DEFAULT_CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
DEFAULT_LEGACY_V1_DATASET = ROOT / "data" / "benchmarks" / "step233c_cn_ranking_challenge_v1.jsonl"
DEFAULT_RANKING_REPORT = ROOT / "artifacts" / "step233c" / "cn_independent_challenge.json"
DEFAULT_TRADEOFF_REPORT = ROOT / "artifacts" / "step233d" / "lite_tradeoff.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "step242a" / "normalized_dev_baselines.json"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Normalize existing v1, D0, and B2 runs under the Step 24.2A metric contract.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--legacy-v1-dataset", type=Path, default=DEFAULT_LEGACY_V1_DATASET)
    parser.add_argument("--ranking-report", type=Path, default=DEFAULT_RANKING_REPORT)
    parser.add_argument("--tradeoff-report", type=Path, default=DEFAULT_TRADEOFF_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    dataset_path = args.dataset.resolve()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("status") != "ANNOTATION_PENDING" or manifest.get("promotionEligible") is not False:
        raise SystemExit("STEP242A_CANDIDATE_MANIFEST_STATE_INVALID")
    if sha256_file(dataset_path) != manifest["files"]["dataset"]["sha256"]:
        raise SystemExit("STEP242A_CANDIDATE_DATASET_HASH_MISMATCH")

    all_cases = [RagQualityCase.model_validate(item) for item in load_jsonl(dataset_path)]
    cases = [item for item in all_cases if item.split == "dev"]
    if len(cases) != 80 or any(item.split == "holdout" for item in cases):
        raise SystemExit("STEP242A_HOLDOUT_EXECUTION_GUARD")

    chunks = load_policy_chunks(args.chunks.resolve())
    chunk_by_id = {item.chunkId: item for item in chunks}
    if content_root_hash(chunks) != manifest["corpus"]["contentRootHash"]:
        raise SystemExit("STEP242A_CORPUS_HASH_MISMATCH")

    legacy_v1 = load_jsonl(args.legacy_v1_dataset.resolve())
    v1_case_id_by_text = {str(item["reviewText"]): str(item["caseId"]) for item in legacy_v1}
    ranking_report = json.loads(args.ranking_report.resolve().read_text(encoding="utf-8-sig"))
    tradeoff_report = json.loads(args.tradeoff_report.resolve().read_text(encoding="utf-8-sig"))

    v1_rows = _rows_by_case(ranking_report, "v1")
    b2_rows = _rows_by_case(ranking_report, "B2")
    d0_rows = _rows_by_case(tradeoff_report, "D0")
    variants = {
        "v1": evaluate_retrieval_run(
            cases,
            build_run(cases, v1_rows, chunk_by_id, v1_case_id_by_text=v1_case_id_by_text),
            run_name="v1_legacy_hybrid_normalized",
        ),
        "D0": evaluate_retrieval_run(
            cases,
            build_run(cases, d0_rows, chunk_by_id),
            run_name="D0_equal_risk_hybrid_normalized",
        ),
        "B2": evaluate_retrieval_run(
            cases,
            build_run(cases, b2_rows, chunk_by_id, v1_case_id_by_text=v1_case_id_by_text),
            run_name="B2_hybrid_reranked_normalized",
        ),
    }
    report = {
        "schemaVersion": "step24.2a-normalized-baseline-v1",
        "gate": "PASS_DIAGNOSTIC",
        "promotionGate": "HOLD",
        "reason": "All labels remain pending human adjudication and Holdout was not executed.",
        "scope": "Existing retrieval artifacts normalized over the 80-case development split only.",
        "dataset": {
            "version": manifest["datasetVersion"],
            "sha256": manifest["files"]["dataset"]["sha256"],
            "devCaseCount": len(cases),
            "holdoutExecuted": False,
        },
        "corpus": manifest["corpus"],
        "sourceArtifacts": {
            "rankingRecovery": {
                "path": str(args.ranking_report.resolve().relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(args.ranking_report.resolve()),
            },
            "liteTradeoff": {
                "path": str(args.tradeoff_report.resolve().relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256_file(args.tradeoff_report.resolve()),
            },
        },
        "variants": variants,
        "limitations": [
            "The development split inherits candidate-exposed partial pooled qrels.",
            "The normalized run consumes existing artifacts and is not a fresh model execution.",
            "Only Top-5 rows are available in the source artifacts, so Recall@10 equals available-depth recall.",
            "The source artifacts contain only 95 risk cases; no-answer abstention is an explicit placeholder and not a measured retrieval result.",
            "No result can authorize candidate promotion before human adjudication and Holdout freeze.",
        ],
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output.resolve(), report)
    print(json.dumps({
        "gate": report["gate"],
        "promotionGate": report["promotionGate"],
        "holdoutExecuted": False,
        "metrics": {name: value["metrics"] for name, value in variants.items()},
    }, ensure_ascii=False, indent=2))
    return 0


def build_run(
    cases: list[RagQualityCase],
    source_rows: dict[str, dict[str, Any]],
    chunk_by_id: dict[str, Any],
    *,
    v1_case_id_by_text: dict[str, str] | None = None,
) -> list[RetrievalRunCase]:
    output: list[RetrievalRunCase] = []
    for case in cases:
        if case.noAnswer:
            output.append(RetrievalRunCase(caseId=case.caseId, abstained=True, hits=[]))
            continue
        source_id = (
            v1_case_id_by_text.get(case.reviewText, "")
            if v1_case_id_by_text is not None
            else str(case.metadata.get("originalCaseId", ""))
        )
        source = source_rows.get(source_id)
        if source is None:
            raise ValueError(f"STEP242A_BASELINE_CASE_NOT_FOUND case={case.caseId} source={source_id}")
        hits = []
        for row in source.get("top5", []):
            chunk_id = str(row["chunkId"])
            chunk = chunk_by_id.get(chunk_id)
            if chunk is None:
                raise ValueError(f"STEP242A_BASELINE_CHUNK_NOT_FOUND chunk={chunk_id}")
            hits.append(
                RetrievalHit(
                    chunkId=chunk_id,
                    score=float(row.get("score", 0.0)),
                    sourceName=chunk.sourceName,
                    sourceUrl=chunk.sourceUrl,
                    sectionPath=chunk.sectionPath,
                    clauseId=chunk.clauseId,
                    contentHash=chunk.contentHash,
                )
            )
        output.append(RetrievalRunCase(caseId=case.caseId, hits=hits, metadata={"sourceCaseId": source_id}))
    return output


def _rows_by_case(report: dict[str, Any], variant: str) -> dict[str, dict[str, Any]]:
    try:
        rows = report["variants"][variant]["caseResults"]
    except KeyError as exc:
        raise ValueError(f"STEP242A_SOURCE_VARIANT_MISSING variant={variant}") from exc
    return {str(row["caseId"]): row for row in rows}


if __name__ == "__main__":
    raise SystemExit(main())
