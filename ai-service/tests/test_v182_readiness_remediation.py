import json
from pathlib import Path

import numpy as np
import pytest

from app.evaluation.v182_readiness_gate import calculate_v182_readiness_gate
from app.observability.soak_event_writer import SoakEvent, SoakEventWriter
from app.rag.dense_provider_factory import DisabledDenseProvider, HashDenseNegativeControlProvider, create_dense_provider
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.sparse_retriever import BM25Retriever

import importlib.util


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ai-service" / "scripts" / "run_v182_remediation_audit.py"
VERIFY = ROOT / "ai-service" / "scripts" / "verify_v182_active_soak.py"


def load_script(path=SCRIPT):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v182_dense_factory_blocks_hash_in_enterprise_mode():
    with pytest.raises(ValueError, match="HASH_DENSE_FORBIDDEN"):
        create_dense_provider(provider_mode="hash_negative_control", enterprise_mode=True, chunks=[])


def test_v182_dense_factory_allows_hash_negative_control_outside_enterprise():
    provider = create_dense_provider(provider_mode="hash_negative_control", enterprise_mode=False, chunks=[chunk("a", "refund")])
    assert provider.provider_mode == "hash_negative_control"


def test_v182_disabled_dense_returns_no_hits():
    assert DisabledDenseProvider().search("refund") == []


def test_v182_disabled_dense_status_marks_sparse_degraded():
    assert DisabledDenseProvider().status()["status"] == "DENSE_UNAVAILABLE_SPARSE_DEGRADED"


def test_v182_hybrid_default_does_not_create_hash_dense():
    retriever = HybridRetriever([chunk("a", "refund policy")])
    assert retriever.status()["provider_mode"] == "disabled"


def test_v182_hybrid_default_still_returns_sparse_hits():
    hits = HybridRetriever([chunk("a", "refund policy")]).search("refund")
    assert hits[0].source == "sparse"


def test_v182_hash_negative_control_status_is_explicit():
    assert HashDenseNegativeControlProvider([]).status()["status"] == "NEGATIVE_CONTROL_ONLY"


def test_v182_unknown_dense_provider_is_rejected():
    with pytest.raises(ValueError, match="UNKNOWN_DENSE_PROVIDER_MODE"):
        create_dense_provider(provider_mode="mystery")


def test_v182_dense_factory_real_bge_missing_index_degrades_sparse():
    provider = create_dense_provider(provider_mode="real_bge_m3", enterprise_mode=True)
    assert provider.provider_mode == "disabled"


def test_v182_hybrid_with_disabled_dense_has_no_dense_rank():
    hit = HybridRetriever([chunk("a", "refund policy")]).search("refund")[0]
    assert hit.dense_rank is None


def test_v182_semantic_pairs_have_sixty_cases():
    assert len(load_script().semantic_pairs()) == 60


def test_v182_semantic_pairs_include_chinese_and_english():
    pairs = load_script().semantic_pairs()
    assert any("电池" in row["query"] for row in pairs)
    assert any("screen" in row["query"] for row in pairs)


def test_v182_surface_doc_does_not_emit_query_id():
    text = load_script().surface_doc(fact(), "policy", "en", 0, __import__("random").Random(1))
    assert "q-" not in text


def test_v182_surface_query_does_not_emit_gold_chunk_id():
    text = load_script().surface_query(fact(), "lexical", __import__("random").Random(1))
    assert "chunk" not in text.lower()


def test_v182_ngram_overlap_identical_text_is_high():
    assert load_script()._ngram_overlap("abcdefghijk", "abcdefghijk") == 1.0


def test_v182_ngram_overlap_unrelated_text_is_low():
    assert load_script()._ngram_overlap("abcdefghijk", "中文售后退款") == 0


def test_v182_eval_hit_at_one_counts_only_top_rank():
    assert load_script()._hit([1, 2, None], 1) == pytest.approx(0.333333)


def test_v182_eval_hit_at_five_counts_rank_five():
    assert load_script()._hit([5, 6, None], 5) == pytest.approx(0.333333)


def test_v182_latency_summary_has_percentiles():
    summary = load_script()._latency([1, 2, 3, 4, 5])
    assert set(summary) == {"p50", "p95", "p99"}


def test_v182_eval_method_reports_empty_rate():
    queries = [{"query_text": "x", "tenant_id": "t", "gold_chunk_id": "missing"}]
    result = load_script()._eval_method(queries, lambda q: [])
    assert result["empty_rate"] == 1.0


def test_v182_eval_method_scores_gold_rank():
    queries = [{"query_text": "x", "tenant_id": "t", "gold_chunk_id": "a"}]
    result = load_script()._eval_method(queries, lambda q: [type("Hit", (), {"chunk_id": "a"})()])
    assert result["hit_at_1"] == 1.0


def test_v182_soak_event_writer_hashes_tenant():
    assert len(SoakEventWriter.tenant_hash("tenant-a")) == 24


def test_v182_soak_event_writer_rejects_forbidden_key(tmp_path):
    writer = SoakEventWriter(tmp_path / "events.jsonl")
    with pytest.raises(ValueError, match="FORBIDDEN_KEY"):
        writer._guard({"prompt": "secret"})


def test_v182_soak_event_writer_writes_jsonl_without_tenant_id(tmp_path):
    writer = SoakEventWriter(tmp_path / "events.jsonl")
    writer.write(event())
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "tenant_id" not in text


def test_v182_soak_event_writer_records_monotonic_ns(tmp_path):
    writer = SoakEventWriter(tmp_path / "events.jsonl")
    row = writer.write(event())
    assert row["monotonic_ns"] > 0


def test_v182_soak_verifier_blocks_short_duration():
    verifier = load_script(VERIFY)
    rows = [minimal_soak_row(i, "retrieval") for i in range(2)]
    assert verifier.verify(rows, 10)["status"] == "V182_90_MIN_ACTIVE_SOAK_BLOCKED"


def test_v182_soak_verifier_counts_request_types():
    verifier = load_script(VERIFY)
    rows = [minimal_soak_row(0, "retrieval"), minimal_soak_row(1, "health")]
    result = verifier.verify(rows, 0)
    assert result["request_counts"]["retrieval"] == 1


def test_v182_soak_verifier_detects_pii_key():
    verifier = load_script(VERIFY)
    row = minimal_soak_row(0, "retrieval")
    row["tenant_id"] = "tenant-a"
    assert verifier.verify([row], 0)["pii_leakage"] == 1


def test_v182_soak_percentile_empty_is_zero():
    assert load_script(VERIFY)._pct([], 0.95) == 0


def test_v182_soak_percentile_returns_ordered_value():
    assert load_script(VERIFY)._pct([1, 2, 3], 0.5) == 2


def test_v182_gate_blocks_when_benchmark_missing():
    payload = gate_payload()
    payload["benchmark"]["status"] = "BLOCKED"
    assert calculate_v182_readiness_gate(payload)["gate"] != "V182_REAL_ENTERPRISE_READINESS_PASS"


def test_v182_gate_allows_local_when_docker_runtime_unavailable():
    payload = gate_payload()
    payload["docker"]["runtime_status"] = "V182_DOCKER_RUNTIME_UNAVAILABLE"
    assert calculate_v182_readiness_gate(payload)["gate"] == "V182_LOCAL_RUNTIME_READINESS_PASS"


def test_v182_gate_full_requires_docker_runtime():
    payload = gate_payload()
    assert calculate_v182_readiness_gate(payload)["gate"] == "V182_REAL_ENTERPRISE_READINESS_PASS"


def test_v182_gate_reports_hash_dense_blocker():
    payload = gate_payload()
    payload["dense"]["enterprise_hash_dense_reachable"] = True
    assert "enterprise_hash_dense_unreachable" in calculate_v182_readiness_gate(payload)["blockers"]


def test_v182_gate_requires_java_real_tests():
    payload = gate_payload()
    payload["java"]["status"] = "V182_JAVA_TESTS_NOT_RUN"
    assert "java_tests" in calculate_v182_readiness_gate(payload)["blockers"]


def test_v182_gate_requires_soak_pass():
    payload = gate_payload()
    payload["soak"]["status"] = "V182_90_MIN_ACTIVE_SOAK_BLOCKED"
    assert "active_soak" in calculate_v182_readiness_gate(payload)["blockers"]


def test_v182_docker_compose_file_has_ai_service_profile():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'profiles: ["ai-service"]' in text


def test_v182_docker_compose_has_healthcheck():
    assert "healthcheck:" in (ROOT / "docker-compose.yml").read_text(encoding="utf-8")


def test_v182_dockerfile_uses_non_root_user():
    assert "USER ereview" in (ROOT / "ai-service" / "Dockerfile").read_text(encoding="utf-8")


def test_v182_dockerfile_does_not_copy_data_private():
    assert "data-private" not in (ROOT / "ai-service" / "Dockerfile").read_text(encoding="utf-8")


def test_v182_java_result_records_twenty_tests():
    path = ROOT / "data" / "private_research" / "audit" / "v182_java_test_result.json"
    if not path.exists():
        pytest.skip("java result generated by integration command")
    assert json.loads(path.read_text(encoding="utf-8"))["tests_run"] >= 20


def test_v182_java_result_does_not_use_skip_flag():
    path = ROOT / "data" / "private_research" / "audit" / "v182_java_test_result.json"
    if not path.exists():
        pytest.skip("java result generated by integration command")
    assert json.loads(path.read_text(encoding="utf-8"))["skip_tests_flag_used"] is False


def test_v182_benchmark_manifest_excludes_full_text_from_git():
    path = ROOT / "data" / "private_research" / "audit" / "v182_benchmark_manifest.json"
    if not path.exists():
        pytest.skip("benchmark manifest generated by audit script")
    assert json.loads(path.read_text(encoding="utf-8"))["git_excludes_full_text"] is True


def test_v182_benchmark_manifest_has_required_fact_count():
    path = ROOT / "data" / "private_research" / "audit" / "v182_benchmark_manifest.json"
    if not path.exists():
        pytest.skip("benchmark manifest generated by audit script")
    assert json.loads(path.read_text(encoding="utf-8"))["fact_count"] >= 700


def test_v182_benchmark_manifest_has_required_query_count():
    path = ROOT / "data" / "private_research" / "audit" / "v182_benchmark_manifest.json"
    if not path.exists():
        pytest.skip("benchmark manifest generated by audit script")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["main_query_count"] + data["security_query_count"] >= 500


def test_v182_benchmark_provenance_has_no_gold_exposure():
    path = ROOT / "data" / "private_research" / "audit" / "v182_benchmark_provenance.json"
    if not path.exists():
        pytest.skip("benchmark provenance generated by audit script")
    assert json.loads(path.read_text(encoding="utf-8"))["gold_id_exposure"] == 0


def test_v182_retrieval_evaluation_hash_is_negative_control_only():
    path = ROOT / "data" / "private_research" / "audit" / "v182_retrieval_evaluation.json"
    if not path.exists():
        pytest.skip("retrieval result generated by audit script")
    assert "hash_negative_control" in json.loads(path.read_text(encoding="utf-8"))["methods"]


def test_v182_retrieval_evaluation_has_zero_tenant_leakage():
    path = ROOT / "data" / "private_research" / "audit" / "v182_retrieval_evaluation.json"
    if not path.exists():
        pytest.skip("retrieval result generated by audit script")
    assert json.loads(path.read_text(encoding="utf-8"))["tenant_leakage"] == 0


def chunk(chunk_id, content):
    return {"tenant_id": "tenant-a", "document_id": chunk_id, "chunk_id": chunk_id, "content": content, "active": True}


def fact():
    return {"fact_id": "fact-1", "tenant_id": "tenant-a", "entity": "sku-1", "relation": "refund_window", "value": "7-days", "version": 1, "trust_level": "internal_verified"}


def event():
    return SoakEvent(
        request_type="retrieval",
        route="/rag/search",
        success=True,
        status_code=200,
        latency_ms=1.0,
        tenant_hash=SoakEventWriter.tenant_hash("tenant-a"),
        index_version="idx",
        provider_mode="sparse",
        memory_rss_mb=1.0,
        cpu_percent=0.0,
        thread_count=1,
        fd_count=1,
        queue_depth=0,
        cache_size=0,
    )


def minimal_soak_row(offset, request_type):
    return {
        "monotonic_ns": offset * 1_000_000_000,
        "request_type": request_type,
        "success": True,
        "latency_ms": 1,
    }


def gate_payload():
    return {
        "dense": {"enterprise_hash_dense_reachable": False},
        "real_bge": {"status": "V182_REAL_BGE_M3_RUNTIME_PASS"},
        "real_bge_faiss": {"status": "V182_REAL_BGE_FAISS_INDEX_PASS"},
        "benchmark": {"status": "V182_BENCHMARK_PROVENANCE_PASS"},
        "retrieval": {"tenant_leakage": 0},
        "soak": {"status": "V182_90_MIN_ACTIVE_SOAK_PASS"},
        "java": {"status": "V182_JAVA_TESTS_REAL_PASS"},
        "docker": {"compose_status": "V182_DOCKER_COMPOSE_STATIC_PASS", "runtime_status": "V182_DOCKER_RUNTIME_PASS"},
        "regression": {"pytest_pass": True, "isolation": "EXTERNAL_TEST_ISOLATION_AUDIT_PASS", "security": "SECURITY_HYGIENE_CHECK_PASS"},
    }
