from __future__ import annotations

from typing import Any


def calculate_v182_readiness_gate(payload: dict[str, Any]) -> dict[str, Any]:
    requirements = {
        "enterprise_hash_dense_unreachable": payload.get("dense", {}).get("enterprise_hash_dense_reachable") is False,
        "real_bge_runtime": payload.get("real_bge", {}).get("status") == "V182_REAL_BGE_M3_RUNTIME_PASS",
        "real_bge_faiss": payload.get("real_bge_faiss", {}).get("status") == "V182_REAL_BGE_FAISS_INDEX_PASS",
        "benchmark_provenance": payload.get("benchmark", {}).get("status") == "V182_BENCHMARK_PROVENANCE_PASS",
        "tenant_leakage_zero": payload.get("retrieval", {}).get("tenant_leakage", 999) == 0,
        "active_soak": payload.get("soak", {}).get("status") == "V182_90_MIN_ACTIVE_SOAK_PASS",
        "java_tests": payload.get("java", {}).get("status") == "V182_JAVA_TESTS_REAL_PASS",
        "docker_compose": payload.get("docker", {}).get("compose_status") == "V182_DOCKER_COMPOSE_STATIC_PASS",
        "pytest": payload.get("regression", {}).get("pytest_pass") is True,
        "isolation": payload.get("regression", {}).get("isolation") == "EXTERNAL_TEST_ISOLATION_AUDIT_PASS",
        "security": payload.get("regression", {}).get("security") == "SECURITY_HYGIENE_CHECK_PASS",
    }
    docker_runtime = payload.get("docker", {}).get("runtime_status")
    full_requirements = {**requirements, "docker_runtime": docker_runtime == "V182_DOCKER_RUNTIME_PASS"}
    blockers = [name for name, ok in requirements.items() if not ok]
    if all(full_requirements.values()):
        gate = "V182_REAL_ENTERPRISE_READINESS_PASS"
    elif not blockers and docker_runtime in {"V182_DOCKER_RUNTIME_UNAVAILABLE", "V182_DOCKER_RUNTIME_PASS"}:
        gate = "V182_LOCAL_RUNTIME_READINESS_PASS"
    elif len(blockers) < len(requirements):
        gate = "V182_READINESS_PARTIAL"
    else:
        gate = "V182_READINESS_BLOCKED"
    return {
        "gate": gate,
        "requirements": requirements,
        "docker_runtime": docker_runtime,
        "blockers": blockers,
        "full_enterprise_gate": all(full_requirements.values()),
        "local_runtime_gate": not blockers,
    }
