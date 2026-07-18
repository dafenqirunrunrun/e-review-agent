from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VERIFIED = {"VERIFIED_REAL"}
PARTIAL = {"VERIFIED_PARTIAL", "VERIFIED_STATIC_ONLY"}
BLOCKING = {"MISSING", "CONTRADICTED", "UNREPRODUCIBLE", "MOCK_ONLY"}


@dataclass(frozen=True)
class GateAuditInput:
    test_depth_pass: bool
    real_dense_status: str
    faiss_status: str
    sparse_status: str
    tenant_leakage_count: int
    benchmark_status: str
    soak_status: str
    failure_injection_status: str
    http_status: str
    java_status: str
    docker_runtime_status: str
    gate_bypass_found: bool


def calculate_independent_v181_gate(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate v1.8.1 readiness without reusing the v1.8.0 final gate.

    The auditor is deliberately conservative: local enterprise readiness is only
    fully verified when runtime evidence exists for dense retrieval, FAISS,
    persistence, tenant isolation, HTTP, soak, failure recovery, Java contract,
    and Docker runtime. Static compose validation is not treated as runtime.
    """

    inputs = GateAuditInput(
        test_depth_pass=bool(payload.get("test_depth", {}).get("pass")),
        real_dense_status=str(payload.get("real_embedding", {}).get("status", "MISSING")),
        faiss_status=str(payload.get("faiss", {}).get("status", "MISSING")),
        sparse_status=str(payload.get("sparse", {}).get("status", "MISSING")),
        tenant_leakage_count=int(payload.get("tenant", {}).get("tenant_leakage_count", 9999)),
        benchmark_status=str(payload.get("benchmark", {}).get("status", "MISSING")),
        soak_status=str(payload.get("soak", {}).get("status", "MISSING")),
        failure_injection_status=str(payload.get("failure_injection", {}).get("status", "MISSING")),
        http_status=str(payload.get("http", {}).get("status", "MISSING")),
        java_status=str(payload.get("java", {}).get("status", "MISSING")),
        docker_runtime_status=str(payload.get("docker", {}).get("runtime_status", "MISSING")),
        gate_bypass_found=bool(payload.get("gate_static_analysis", {}).get("bypass_found")),
    )

    blockers: list[str] = []
    partials: list[str] = []
    if not inputs.test_depth_pass:
        blockers.append("test_depth")
    if inputs.tenant_leakage_count != 0:
        blockers.append("tenant_isolation")
    for name, status in [
        ("real_dense", inputs.real_dense_status),
        ("faiss", inputs.faiss_status),
        ("sparse", inputs.sparse_status),
        ("benchmark", inputs.benchmark_status),
        ("soak", inputs.soak_status),
        ("failure_injection", inputs.failure_injection_status),
        ("http", inputs.http_status),
        ("java", inputs.java_status),
        ("docker_runtime", inputs.docker_runtime_status),
    ]:
        if status in BLOCKING or status.endswith("_BLOCKED") or status.endswith("_FAIL"):
            blockers.append(name)
        elif status in PARTIAL or status.endswith("_PARTIAL") or status.endswith("_UNAVAILABLE"):
            partials.append(name)
    if inputs.gate_bypass_found:
        blockers.append("gate_bypass")

    if blockers:
        status = "V180_READINESS_BLOCKED"
    elif partials:
        status = "V180_LOCAL_READINESS_PARTIALLY_VERIFIED"
    else:
        status = "V180_REAL_ENTERPRISE_READINESS_VERIFIED"

    return {
        "independent_gate": status,
        "blockers": blockers,
        "partials": partials,
        "input": inputs.__dict__,
    }
