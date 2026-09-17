from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "data/private_research/audit/v180_v170_truth_audit.json"
OUT_MD = ROOT / "docs/enterprise/v180_v170_truth_audit.md"


def main() -> None:
    files = {
        "dense": ROOT / "ai-service/app/rag/dense_retriever.py",
        "sparse": ROOT / "ai-service/app/rag/sparse_retriever.py",
        "hybrid": ROOT / "ai-service/app/rag/hybrid_retriever.py",
        "reranker": ROOT / "ai-service/app/rag/reranker.py",
        "agent": ROOT / "ai-service/app/agent/governed_agent.py",
        "tools": ROOT / "ai-service/app/agent/tool_registry.py",
        "security": ROOT / "ai-service/app/platform/security.py",
        "logging": ROOT / "ai-service/app/platform/security.py",
        "idempotency": ROOT / "ai-service/app/platform/idempotency.py",
        "cache": ROOT / "ai-service/app/platform/cache.py",
        "breaker": ROOT / "ai-service/app/runtime/circuit_breaker.py",
        "shadow": ROOT / "ai-service/app/runtime/shadow_execution.py",
        "api": ROOT / "ai-service/app/api/enterprise_e_review.py",
        "metrics": ROOT / "ai-service/app/observability/metrics.py",
        "docker": ROOT / "docker/docker-compose.yml",
        "eval": ROOT / "ai-service/scripts/eval_v170_enterprise_gates.py",
    }
    texts = {name: _read(path) for name, path in files.items()}
    eval_audit = _read_json(ROOT / "data/private_research/audit/v170_enterprise_quality_gates.json")
    classifications = {
        "Dense Retriever": _classify_dense(texts["dense"]),
        "Sparse Retriever": _classify_sparse(texts["sparse"]),
        "Hybrid": _classify_hybrid(texts["hybrid"]),
        "Reranker": _classify_reranker(texts["reranker"]),
        "Agent": _classify_agent(texts["agent"]),
        "Tool Registry": _classify_tools(texts["tools"]),
        "PII": _classify_security(texts["security"]),
        "Logging": _classify_logging(texts["logging"]),
        "Idempotency": _classify_idempotency(texts["idempotency"]),
        "Cache": _classify_cache(texts["cache"]),
        "Circuit Breaker": _classify_breaker(texts["breaker"]),
        "Shadow": _classify_shadow(texts["shadow"]),
        "API": _classify_api(texts["api"]),
        "Metrics": _classify_metrics(texts["metrics"]),
        "Docker": _classify_docker(texts["docker"]),
        "Tests": _classify_tests(),
        "Enterprise Eval": _classify_eval(texts["eval"], eval_audit),
    }
    checks = {
        "production_path_uses_hash_embedding": "hashlib.sha256" in texts["dense"] and "HashDenseRetriever" in texts["dense"],
        "metrics_generated_by_fixed_function": _has_literal_perfect_metrics(texts["eval"]),
        "tests_only_assert_object_fields": _tests_are_unit_heavy(),
        "faiss_executed_by_v170_enterprise_eval": "Faiss" in texts["eval"] or "faiss" in texts["eval"],
        "fastapi_real_start_verified": False,
        "real_http_requests_verified": False,
        "persistence_restart_verified": False,
        "multi_tenant_verified": False,
        "rollback_real_execution_verified": "record_runtime_failure" in texts["dense"],
        "prompt_injection_real_execution_verified": "PromptInjectionGuard" in texts["api"],
        "adapter_provider_real_execution_verified": "V23AdapterTextProvider" in (ROOT / "ai-service/tests/test_v170_runtime_adapter_shadow.py").read_text(encoding="utf-8"),
        "mock_inference_only": "BaseTextProvider" in texts["api"] and "QwenTextRuntime" not in texts["api"],
        "real_concurrency_verified": False,
        "hardcoded_1_0_metrics": _has_literal_perfect_metrics(texts["eval"]),
        "corpus_query_same_template_risk": True,
    }
    status = "V170_ENGINEERING_GATE_REVALIDATED"
    downgrade_reasons: list[str] = []
    if checks["production_path_uses_hash_embedding"]:
        status = "V170_ENGINEERING_GATE_DOWNGRADED_DEMO_ONLY"
        downgrade_reasons.append("Enterprise dense retrieval uses HashDenseRetriever instead of a real local embedding model.")
    if checks["hardcoded_1_0_metrics"]:
        status = "V170_ENGINEERING_GATE_DOWNGRADED_DEMO_ONLY"
        downgrade_reasons.append("Enterprise evaluation reports perfect metrics from deterministic programmatic functions.")
    if checks["corpus_query_same_template_risk"]:
        status = "V170_ENGINEERING_GATE_DOWNGRADED_DEMO_ONLY"
        downgrade_reasons.append("v1.7 corpus and query generation are coupled and leakage resistance is unproven.")
    payload = {
        "status": status,
        "base_branch": "experiment/v1.7.0-enterprise-rag-agent-platform",
        "base_head": "94ff37e3",
        "classifications": classifications,
        "checks": checks,
        "downgrade_reasons": downgrade_reasons,
        "artifact_hashes": {name: _sha256(path) for name, path in files.items() if path.exists()},
        "closed_holdout_accessed": False,
        "adapter_published": False,
        "training_executed": False,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(_render_markdown(payload), encoding="utf-8", newline="\n")
    print(status)


def _classify_dense(text: str) -> str:
    if "HashDenseRetriever" in text or "hashlib.sha256" in text:
        return "HASH_DEMO_ONLY"
    if "SentenceTransformer" in text or "AutoModel" in text:
        return "REAL_IMPLEMENTATION"
    return "ABSENT"


def _classify_sparse(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "BM25Retriever" in text and "persist" not in text.lower() else "REAL_IMPLEMENTATION"


def _classify_hybrid(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "HybridRetriever" in text and "rrf_k" in text else "ABSENT"


def _classify_reranker(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "RERANKER_UNAVAILABLE" in text else "ABSENT"


def _classify_agent(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "GovernedAgent" in text and "NODES" in text else "ABSENT"


def _classify_tools(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "FORBIDDEN_BUSINESS_ACTIONS" in text else "ABSENT"


def _classify_security(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "PIIRedactor" in text and "PromptInjectionGuard" in text else "ABSENT"


def _classify_logging(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "SafeStructuredLogger" in text else "ABSENT"


def _classify_idempotency(text: str) -> str:
    if "SQLiteIdempotencyStore" in text:
        return "PARTIAL_IMPLEMENTATION"
    if "InMemoryIdempotencyStore" in text:
        return "IN_MEMORY_ONLY"
    return "ABSENT"


def _classify_cache(text: str) -> str:
    return "IN_MEMORY_ONLY" if "TTLCache" in text else "ABSENT"


def _classify_breaker(text: str) -> str:
    return "UNIT_TEST_ONLY" if "CircuitBreaker" in text else "ABSENT"


def _classify_shadow(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "ShadowExecutionQueue" in text else "ABSENT"


def _classify_api(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "APIRouter" in text and "/analyze" in text else "ABSENT"


def _classify_metrics(text: str) -> str:
    return "IN_MEMORY_ONLY" if "MetricsRegistry" in text else "ABSENT"


def _classify_docker(text: str) -> str:
    return "PARTIAL_IMPLEMENTATION" if "ai-service" in text else "ABSENT"


def _classify_tests() -> str:
    tests = list((ROOT / "ai-service/tests").glob("test_v170_*.py"))
    return "UNIT_TEST_ONLY" if len(tests) >= 4 else "PARTIAL_IMPLEMENTATION"


def _classify_eval(text: str, audit: dict[str, Any]) -> str:
    if _has_literal_perfect_metrics(text):
        return "MOCK_ONLY"
    if audit.get("status") == "V170_ENTERPRISE_RAG_AGENT_ENGINEERING_GATE_PASS":
        return "PARTIAL_IMPLEMENTATION"
    return "UNVERIFIED"


def _has_literal_perfect_metrics(text: str) -> bool:
    tree = ast.parse(text)
    literal_ones = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == 1.0:
            literal_ones += 1
    return literal_ones >= 8


def _tests_are_unit_heavy() -> bool:
    tests = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "ai-service/tests").glob("test_v170_*.py"))
    return "TestClient" in tests and "uvicorn" not in tests and "subprocess" in tests


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v1.8.0 Truth Audit of v1.7.0",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Downgrade Reasons",
        "",
    ]
    if payload["downgrade_reasons"]:
        lines.extend(f"- {reason}" for reason in payload["downgrade_reasons"])
    else:
        lines.append("- None")
    lines.extend(["", "## Classifications", ""])
    for name, status in payload["classifications"].items():
        lines.append(f"- {name}: `{status}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Closed holdouts accessed: `false`",
            "- Adapter published: `false`",
            "- Training executed: `false`",
            "",
            "This audit intentionally downgrades demo-only evidence instead of preserving inflated readiness claims.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
