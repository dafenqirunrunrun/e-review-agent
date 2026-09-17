from __future__ import annotations

import hashlib
import json
import sys
import argparse
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.models import PolicyChunk
from app.rag_quality.models import QualityQrel, RagQualityCase
from scripts.build_step242g_after_sales_semantic_cases import normalize_for_anchor_match, sha256_file


SEMANTIC_DIR = ROOT / "data" / "benchmarks" / "rag_quality_after_sales_semantic_v2"
SEMANTIC_DATASET = SEMANTIC_DIR / "semantic_cases_llm_adjudicated_v2.jsonl"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index_step242g_candidate" / "policy_chunks.jsonl"
OUTPUT_DIR = ROOT / "artifacts" / "step242g_after_sales_semantic" / "bound_candidate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind chunk-independent semantic qrels to a candidate policy index.")
    parser.add_argument("--semantic-dataset", type=Path, default=SEMANTIC_DATASET)
    parser.add_argument("--chunks", type=Path, default=CHUNKS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    semantic_rows = load_jsonl(args.semantic_dataset)
    chunks = load_policy_chunks(args.chunks)
    cases, binding = materialize(semantic_rows, chunks, semantic_dataset=args.semantic_dataset)
    validate_cases(cases, chunks, binding)
    write_outputs(cases, chunks, binding, output_dir=args.output_dir)
    print(json.dumps(binding, ensure_ascii=False, indent=2))
    return 0


def materialize(
    rows: list[dict[str, Any]],
    chunks: list[PolicyChunk],
    *,
    semantic_dataset: Path = SEMANTIC_DATASET,
) -> tuple[list[RagQualityCase], dict[str, Any]]:
    chunks_by_clause: dict[tuple[str, str], list[PolicyChunk]] = {}
    for chunk in chunks:
        chunks_by_clause.setdefault((chunk.documentId, chunk.clauseId), []).append(chunk)
    cases: list[RagQualityCase] = []
    bindings: list[dict[str, Any]] = []
    for row in rows:
        direct_ids: set[str] = set()
        related_ids: set[str] = set()
        reference_rows: list[dict[str, Any]] = []
        for reference in row["expectedEvidence"]:
            key = (str(reference["documentId"]), str(reference["clauseId"]))
            clause_chunks = chunks_by_clause.get(key, [])
            anchors = [normalize_for_anchor_match(str(anchor)) for anchor in reference["requiredAnchors"]]
            matching = [
                chunk
                for chunk in clause_chunks
                if all(anchor in normalize_for_anchor_match(chunk.text) for anchor in anchors)
            ]
            contextual = [chunk for chunk in matching if has_standalone_clause_context(chunk, reference["clauseId"])]
            direct_ids.update(chunk.chunkId for chunk in contextual)
            related_ids.update(chunk.chunkId for chunk in clause_chunks if chunk.chunkId not in direct_ids)
            reference_rows.append(
                {
                    "documentId": key[0],
                    "clauseId": key[1],
                    "requiredAnchors": reference["requiredAnchors"],
                    "clauseChunkCount": len(clause_chunks),
                    "anchorMatchedChunkIds": [chunk.chunkId for chunk in matching],
                    "standaloneDirectChunkIds": [chunk.chunkId for chunk in contextual],
                }
            )
        qrels = [
            QualityQrel(
                chunkId=chunk.chunkId,
                relevance=3 if chunk.chunkId in direct_ids else 1 if chunk.chunkId in related_ids else 0,
                supports=["after_sales_risk"] if chunk.chunkId in direct_ids else [],
                sourceName=chunk.sourceName,
                sourceType=chunk.sourceType,
                sourceLevel="A" if chunk.sourceType in {"law", "regulation"} else "B",
                clauseId=chunk.clauseId,
                rationale=(
                    "Direct semantic evidence with complete required anchors and standalone clause context."
                    if chunk.chunkId in direct_ids
                    else "Same canonical clause but incomplete for this case."
                    if chunk.chunkId in related_ids
                    else "Not sufficient evidence for this case."
                ),
            )
            for chunk in chunks
        ]
        no_answer = bool(row["noAnswer"])
        cases.append(
            RagQualityCase(
                datasetVersion=str(row["datasetVersion"]),
                caseId=str(row["caseId"]),
                split=str(row["split"]),
                reviewText=str(row["reviewText"]),
                queryStyle=str(row["queryStyle"]),
                riskTypes=[str(item) for item in row["riskTypes"]],
                riskLevel=str(row["riskLevel"]),
                noAnswer=no_answer,
                sourceLanguage="not_applicable" if no_answer else "zh",
                documentFormat="not_applicable" if no_answer else "pdf",
                qrels=qrels,
                qrelCompleteness="complete",
                annotationStatus="llm_adjudicated",
                annotationSource=str(row["annotationSource"]),
                candidateExposure=bool(row["candidateExposure"]),
                requiresAdjudication=False,
                metadata={
                    **dict(row.get("metadata") or {}),
                    "semanticBindings": reference_rows,
                    "semanticDatasetVersion": row["datasetVersion"],
                    "boundCorpusChunkCount": len(chunks),
                },
            )
        )
        bindings.append({"caseId": row["caseId"], "references": reference_rows})
    return cases, {
        "schemaVersion": "rag-quality-semantic-binding-v1",
        "datasetVersion": rows[0]["datasetVersion"] if rows else "",
        "semanticDatasetSha256": sha256_file(semantic_dataset),
        "candidateCorpusContentRootHash": content_root_hash(chunks),
        "candidateCorpusChunkCount": len(chunks),
        "caseBindings": bindings,
        "status": "BOUND_CANDIDATE_AWAITING_DEV_RUN",
        "limitation": "Semantic labels are single-Codex-adjudicated and corpus binding is candidate-only; not human gold.",
    }


def validate_cases(cases: list[RagQualityCase], chunks: list[PolicyChunk], binding: dict[str, Any]) -> None:
    corpus_ids = {chunk.chunkId for chunk in chunks}
    failed_refs = [
        {"caseId": item["caseId"], "reference": reference}
        for item in binding["caseBindings"]
        for reference in item["references"]
        if not reference["standaloneDirectChunkIds"]
    ]
    checks = {
        "candidateCorpusIsNonEmpty": bool(chunks),
        "caseCountIs48": len(cases) == 48,
        "fullQrels": all(len(case.qrels) == len(chunks) and {qrel.chunkId for qrel in case.qrels} == corpus_ids for case in cases),
        "riskCasesBindDirectEvidence": all(any(qrel.relevance == 3 for qrel in case.qrels) for case in cases if not case.noAnswer),
        "normalCasesHaveNoPositiveQrels": all(not any(qrel.relevance >= 2 for qrel in case.qrels) for case in cases if case.noAnswer),
        "holdoutNotCandidateExposed": all(not case.candidateExposure for case in cases if case.split == "holdout"),
        "allSemanticReferencesBindStandaloneEvidence": not failed_refs,
    }
    if not all(checks.values()):
        raise ValueError(f"STEP242G_QREL_BINDING_INVALID checks={checks} failures={failed_refs}")


def has_standalone_clause_context(chunk: PolicyChunk, clause_id: str) -> bool:
    expected = f"第{clause_id}条"
    return bool(
        chunk.metadata.get("clauseContext") == expected
        and normalize_for_anchor_match(chunk.text).startswith(normalize_for_anchor_match(expected))
    )


def write_outputs(
    cases: list[RagQualityCase],
    chunks: list[PolicyChunk],
    binding: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = output_dir / "dataset_bound_candidate_v2.jsonl"
    dev = output_dir / "dev_bound_candidate_v2.jsonl"
    holdout = output_dir / "holdout_bound_candidate_v2.jsonl"
    qrels = output_dir / "qrels_bound_candidate_v2.tsv"
    write_jsonl(dataset, [case.model_dump(mode="json") for case in cases])
    write_jsonl(dev, [case.model_dump(mode="json") for case in cases if case.split == "dev"])
    write_jsonl(holdout, [case.model_dump(mode="json") for case in cases if case.split == "holdout"])
    qrels.write_text(
        "".join(f"{case.caseId}\t0\t{qrel.chunkId}\t{qrel.relevance}\n" for case in cases for qrel in case.qrels),
        encoding="utf-8",
        newline="\n",
    )
    binding["files"] = {
        path.name: {"path": path.name, "sha256": sha256_file(path)}
        for path in (dataset, dev, holdout, qrels)
    }
    write_json(output_dir / "binding_manifest_v2.json", binding)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def content_root_hash(chunks: list[PolicyChunk]) -> str:
    return hashlib.sha256("|".join(chunk.contentHash for chunk in chunks).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
