import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a2_common import (
    benchmark_integrity,
    no_answer_gate,
    phase3a2_cases,
    rrf_contribution,
    select_default_mode,
    split_cases,
)
from agent_rag_phase3a_common import phase3a_all_tenant_chunks
from app.agent_rag.embedding_provider import HashEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.phase2_retrieval import RetrievalCandidate


def test_v200_phase3a2_benchmark_classification_and_counts():
    _, chunks = phase3a_all_tenant_chunks()
    cases = phase3a2_cases(chunks)
    integrity = benchmark_integrity(cases, chunks)
    assert integrity["status"] == "PASS"
    assert integrity["caseCount"] >= 150
    assert integrity["semanticCount"] >= 40
    assert integrity["lexicalCount"] >= 40
    assert integrity["mixedCount"] >= 30
    assert integrity["negativeNoAnswerCount"] >= 10


def test_v200_phase3a2_stable_stratified_split():
    _, chunks = phase3a_all_tenant_chunks()
    cases = phase3a2_cases(chunks)
    first = split_cases(cases)
    second = split_cases(cases)
    assert first["calibrationCaseIdsHash"] == second["calibrationCaseIdsHash"]
    assert first["evaluationCaseIdsHash"] == second["evaluationCaseIdsHash"]
    assert {case["caseId"] for case in first["calibration"]}.isdisjoint({case["caseId"] for case in first["evaluation"]})


def test_v200_phase3a2_rrf_contribution_and_weighted_rrf():
    sparse = [RetrievalCandidate("sparse", "tenant-a", "d1", "c1", sparseRank=1), RetrievalCandidate("sparse", "tenant-a", "d2", "c2", sparseRank=2)]
    dense = [RetrievalCandidate("dense", "tenant-a", "d3", "c3", denseRank=1), RetrievalCandidate("dense", "tenant-a", "d1", "c1", denseRank=2)]
    base = rrf_contribution(sparse, dense, sparse_weight=1.0, dense_weight=1.0)
    weighted = rrf_contribution(sparse, dense, sparse_weight=1.0, dense_weight=1.5)
    assert base[0]["finalFusionScore"] > 0
    assert any(row["chunkId"] == "c3" and row["denseContribution"] > 0 for row in weighted)
    assert sum(row["denseContribution"] for row in weighted) > sum(row["denseContribution"] for row in base)


def test_v200_phase3a2_no_answer_rejection():
    rows = [
        {
            "retrievalChallengeType": "negative/no-answer",
            "tenantId": "tenant-a",
            "hybridTop5": [{"chunkId": "c1", "documentId": "d1", "tenantId": "tenant-a", "fusionScore": 0.01}],
        }
    ]
    result = no_answer_gate(rows, min_score=1.0)
    assert result["falseEvidenceRate"] == 0
    assert result["noAnswerCorrectRejectionRate"] == 1.0


def test_v200_phase3a2_default_mode_selection_requires_evidence():
    summary = {
        "subsets": {
            "overall": {
                "bm25": {"ndcgAt5": 0.55, "recallAt5": 0.47},
                "bge": {"ndcgAt5": 0.10, "recallAt5": 0.12},
                "hybrid": {"ndcgAt5": 0.55, "recallAt5": 0.47},
            },
            "semantic": {
                "bm25": {"ndcgAt5": 0.40, "recallAt5": 0.30},
                "bge": {"ndcgAt5": 0.30, "recallAt5": 0.20},
                "hybrid": {"ndcgAt5": 0.40, "recallAt5": 0.30},
            },
        }
    }
    mode, conclusion = select_default_mode(summary)
    assert mode == "sparse-only"
    assert conclusion == "AGENT_RAG_DENSE_QUALITY_GAIN_NOT_DEMONSTRATED"


def test_v200_phase3a2_numpy_vs_faiss_topk_and_mapping(tmp_path):
    _, chunks = phase3a_all_tenant_chunks()
    chunks = chunks[:12]
    provider = HashEmbeddingProvider(dimensions=32)
    index = FaissVectorIndex(tmp_path / "faiss")
    manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="hash-v1")
    index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
    loaded, rows, _ = index.load_active(provider.metadata(), tenant_id="tenant-a")
    query = provider.embed_query("refund broken after-sales")
    scores, ids = loaded.search(query, 5)
    vectors = provider.embed_documents([row["text"] for row in rows])
    brute_scores = vectors @ query[0]
    brute_ids = np.argsort(-brute_scores)[:5]
    assert np.allclose(sorted(scores[0], reverse=True), sorted(brute_scores[brute_ids], reverse=True), atol=1e-5)
    assert all(int(row["vectorPosition"]) == index for index, row in enumerate(rows))


def test_v200_phase3a2_sanity_fixture_has_30_groups():
    path = ROOT / "ai-service" / "tests" / "fixtures" / "agent_rag" / "phase3a2_sanity" / "sanity_cases.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) >= 30
    assert all({"query", "positive", "hardNegative", "easyNegative", "tenant", "expectedOrdering"}.issubset(row) for row in rows)


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a2_embedding_health_script_real_dense():
    if not os.getenv("RAG_BGE_M3_MODEL_PATH"):
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    completed = subprocess.run([sys.executable, "ai-service/scripts/diagnostics/run_bge_m3_embedding_health.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "AGENT_RAG_EMBEDDING_HEALTH_PASS" in completed.stdout


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a2_gate_real_dense():
    if not os.getenv("RAG_BGE_M3_MODEL_PATH"):
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    completed = subprocess.run([sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase3a2_gate.py"], cwd=ROOT, text=True, capture_output=True, check=True, timeout=900)
    assert "AGENT_RAG_PHASE3A2_PASS" in completed.stdout
