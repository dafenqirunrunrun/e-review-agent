#!/usr/bin/env python
"""Run deterministic local knowledge scale qualification without real customer data."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
QUERIES = [
    ("after_sales", "refund replacement warranty", "tenant-001"),
    ("logistics", "shipping delivery tracking delay", "tenant-002"),
    ("review_risk", "prompt injection fake review pii", "tenant-003"),
    ("quality", "battery screen material quality", "tenant-004"),
    ("policy", "return policy citation evidence", "tenant-005"),
    ("neutral", "usage guide product description", "tenant-006"),
]


@dataclass
class Chunk:
    chunk_id: str
    tenant_id: str
    visibility: str
    active: bool
    expired: bool
    topic: str
    text: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            chunks.append(
                Chunk(
                    chunk_id=row["chunkId"],
                    tenant_id=row["tenantId"],
                    visibility=row["visibility"],
                    active=bool(row["active"]),
                    expired=bool(row["expired"]),
                    topic=row["topic"],
                    text=row["text"],
                )
            )
    return chunks


def _build_index(chunks: list[Chunk]) -> tuple[dict[str, list[int]], dict[int, Counter[str]]]:
    postings: dict[str, list[int]] = defaultdict(list)
    doc_terms: dict[int, Counter[str]] = {}
    for idx, chunk in enumerate(chunks):
        counts = Counter(_tokens(chunk.text))
        doc_terms[idx] = counts
        for token in counts:
            postings[token].append(idx)
    return postings, doc_terms


def _search(
    query: str,
    tenant_id: str,
    chunks: list[Chunk],
    postings: dict[str, list[int]],
    doc_terms: dict[int, Counter[str]],
    top_k: int = 5,
) -> list[tuple[float, Chunk]]:
    q_terms = Counter(_tokens(query))
    candidate_ids: set[int] = set()
    for term in q_terms:
        candidate_ids.update(postings.get(term, []))
    scored: list[tuple[float, Chunk]] = []
    total_docs = max(1, len(chunks))
    for idx in candidate_ids:
        chunk = chunks[idx]
        if not chunk.active or chunk.expired:
            continue
        if chunk.visibility != "public" and chunk.tenant_id != tenant_id:
            continue
        score = 0.0
        terms = doc_terms[idx]
        for term, q_count in q_terms.items():
            tf = terms.get(term, 0)
            if not tf:
                continue
            df = len(postings.get(term, []))
            idf = math.log((1 + total_docs) / (1 + df)) + 1.0
            score += q_count * tf * idf
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].chunk_id))
    return scored[:top_k]


def _dcg(relevance: Iterable[int]) -> float:
    return sum((2**rel - 1) / math.log2(index + 2) for index, rel in enumerate(relevance))


def _metrics(chunks: list[Chunk], postings: dict[str, list[int]], doc_terms: dict[int, Counter[str]]) -> dict[str, object]:
    ndcgs: list[float] = []
    reciprocal_ranks: list[float] = []
    recall_hits = 0
    tenant_violations = 0
    inactive_leakage = 0
    expired_leakage = 0
    duplicate_evidence = 0
    latencies_ms: list[float] = []
    for expected_topic, query, tenant_id in QUERIES:
        started = time.perf_counter()
        results = _search(query, tenant_id, chunks, postings, doc_terms)
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        relevance = [1 if chunk.topic == expected_topic else 0 for _, chunk in results]
        ideal = sorted(relevance, reverse=True)
        ndcgs.append(_dcg(relevance) / _dcg(ideal) if any(ideal) else 0.0)
        reciprocal_ranks.append(next((1.0 / (idx + 1) for idx, rel in enumerate(relevance) if rel), 0.0))
        recall_hits += 1 if any(relevance) else 0
        seen: set[str] = set()
        for _, chunk in results:
            if chunk.visibility != "public" and chunk.tenant_id != tenant_id:
                tenant_violations += 1
            if not chunk.active:
                inactive_leakage += 1
            if chunk.expired:
                expired_leakage += 1
            if chunk.chunk_id in seen:
                duplicate_evidence += 1
            seen.add(chunk.chunk_id)
    sorted_latencies = sorted(latencies_ms)
    p95 = sorted_latencies[min(len(sorted_latencies) - 1, math.ceil(len(sorted_latencies) * 0.95) - 1)]
    return {
        "nDCG@5": round(sum(ndcgs) / len(ndcgs), 6),
        "MRR": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 6),
        "Recall@5": round(recall_hits / len(QUERIES), 6),
        "queryP95Ms": round(p95, 6),
        "tenantViolations": tenant_violations,
        "inactiveLeakage": inactive_leakage,
        "expiredLeakage": expired_leakage,
        "duplicateEvidence": duplicate_evidence,
    }


def _run_generator(repo_root: Path, chunks: int, tenants: int, seed: int, output: Path) -> None:
    script = repo_root / "ai-service" / "scripts" / "qualification" / "generate_scale_knowledge.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--chunks",
            str(chunks),
            "--tenants",
            str(tenants),
            "--seed",
            str(seed),
            "--output",
            str(output),
        ],
        check=True,
        cwd=str(repo_root),
    )


def _qualify(repo_root: Path, artifact_root: Path, chunks: int, tenants: int, seed: int) -> dict[str, object]:
    data_path = artifact_root / "generated" / f"scale-{chunks}.jsonl"
    started_generation = time.perf_counter()
    _run_generator(repo_root, chunks, tenants, seed, data_path)
    generation_s = time.perf_counter() - started_generation

    started_load = time.perf_counter()
    loaded = _load_chunks(data_path)
    load_s = time.perf_counter() - started_load

    started_index = time.perf_counter()
    postings, doc_terms = _build_index(loaded)
    index_s = time.perf_counter() - started_index
    metrics = _metrics(loaded, postings, doc_terms)
    pass_status = (
        metrics["tenantViolations"] == 0
        and metrics["inactiveLeakage"] == 0
        and metrics["expiredLeakage"] == 0
        and metrics["duplicateEvidence"] == 0
        and metrics["nDCG@5"] >= 0.95
        and metrics["MRR"] >= 0.95
        and metrics["Recall@5"] >= 0.95
    )
    return {
        "chunks": chunks,
        "tenants": tenants,
        "syntheticOnly": True,
        "generatedDataCommitted": False,
        "rawDataSizeBytes": data_path.stat().st_size,
        "generationSeconds": round(generation_s, 6),
        "loadSeconds": round(load_s, 6),
        "indexBuildSeconds": round(index_s, 6),
        "indexTermCount": len(postings),
        "metrics": metrics,
        "status": "PASS" if pass_status else "BLOCKED",
        "manifestHash": json.loads(data_path.with_suffix(data_path.suffix + ".manifest.json").read_text(encoding="utf-8"))["hash"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scales", nargs="+", type=int, default=[1000, 10000, 100000])
    parser.add_argument("--tenants", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2100)
    parser.add_argument("--artifact-root", default=os.environ.get("E_REVIEW_QUALIFICATION_ROOT", r"D:\EReviewAgent\qualification\v2.1\scale"))
    parser.add_argument("--output", default="artifacts/qualification/scale-qualification-summary.json")
    args = parser.parse_args()

    repo_root = Path.cwd()
    artifact_root = Path(args.artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=True)
    results = [_qualify(repo_root, artifact_root, scale, args.tenants, args.seed + scale) for scale in args.scales]
    summary = {
        "schemaVersion": "v2.1-scale-qualification",
        "generatedAt": _utc_now(),
        "artifactRootClass": "external-qualification-directory",
        "scales": results,
        "tokens": [],
    }
    for item in results:
        if item["status"] == "PASS":
            summary["tokens"].append(f"AGENT_RAG_SCALE_{int(item['chunks'] / 1000)}K_PASS")
        else:
            summary["tokens"].append(f"AGENT_RAG_SCALE_{int(item['chunks'] / 1000)}K_BLOCKED")
    if not any(item["chunks"] >= 1000000 for item in results):
        summary["tokens"].append("MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for token in summary["tokens"]:
        print(token)
    print(f"SCALE_QUALIFICATION_WRITTEN {output.as_posix()}")
    return 0 if all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
