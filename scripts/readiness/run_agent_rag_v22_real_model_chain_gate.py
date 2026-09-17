from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "real-model-chain" / "v22-real-model-chain-gate.json"


def main() -> int:
    e2e = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-model-chain-e2e-summary.json")
    soak = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-model-soak-summary.json")
    reranker = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-reranker-gate.json")
    reranker_eval = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-reranker-benchmark-summary.json")
    llm = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-llm-gate.json")
    marker = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-real-marker-regression-gate.json")
    admin_lint = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-admin-lint-regression-gate.json")
    full = read_json(ROOT / "artifacts" / "real-model-chain" / "v22-full-regression-summary.json")
    model_quality = {
        "realRerankerQualityImproved": reranker_eval.get("qualityDecision") == "AGENT_RAG_V22_REAL_RERANKER_QUALITY_IMPROVED",
        "realRerankerQualityParityOnly": reranker_eval.get("qualityDecision") == "AGENT_RAG_V22_REAL_RERANKER_PARITY_ONLY",
        "realRerankerQualityRegression": reranker_eval.get("qualityDecision") == "AGENT_RAG_V22_REAL_RERANKER_QUALITY_REGRESSION",
        "realLlmQualityVerified": llm.get("status") == "PASS",
    }
    runtime_correctness = {
        "environmentPass": (ROOT / "artifacts" / "real-model-chain" / "python-environment-gate.json").exists()
        or (ROOT / "artifacts" / "real-model-chain" / "v22-python-environment-gate.json").exists(),
        "assetsPass": asset_manifest_exists(),
        "realEmbeddingPass": e2e.get("realBgeExecutions", 0) > 0 or soak.get("realBgeExecutions", 0) > 0,
        "realRerankerRuntimePass": bool(reranker.get("checks", {}).get("runtimeIntegrationPass")) or e2e.get("realRerankerExecutions", 0) > 0 or soak.get("realRerankerExecutions", 0) > 0,
        "realLlmRuntimePass": llm.get("status") == "PASS",
        "gpuResidencyPass": soak.get("status") == "PASS" and soak.get("activeRequestsFinal", 1) == 0 and soak.get("queueFinal", 1) == 0,
        "javaE2ePass": e2e.get("status") == "PASS" and e2e.get("realFullChainSuccessfulRuns", 0) > 0,
        "soakPass": soak.get("status") == "PASS",
        "markerRegressionPass": marker.get("status") == "PASS",
        "pythonPass": full.get("pythonDefaultPass") is True,
        "javaPass": full.get("javaPass") is True and full.get("javaPackagePass") is True,
        "adminUnitPass": full.get("adminUnitTestPass") is True,
        "adminBuildPass": full.get("adminBuildPass") is True,
        "adminNoNewLintPass": admin_lint.get("status") == "PASS" and admin_lint.get("newErrorCount") == 0,
        "h5BuildPass": full.get("h5BuildPass") is True,
    }
    legacy_repository_debt = {
        "adminLegacyLintDebt": admin_lint.get("legacyLintDebt", 0),
        "adminFullLintClean": admin_lint.get("fullLintClean") is True,
        "adminNpmCiUnavailable": full.get("adminNpmCiPass") is False,
        "h5NpmCiUnavailable": full.get("h5NpmCiPass") is False,
        "cleanVerificationPass": full.get("cleanVerificationPass") is True,
    }
    checks = {
        **model_quality,
        **runtime_correctness,
        "adminLegacyLintSeparated": admin_lint.get("legacyLintDebt", 0) >= 0,
    }
    required = [
        *runtime_correctness.values(),
        model_quality["realRerankerQualityImproved"],
        model_quality["realLlmQualityVerified"],
    ]
    status = "PASS" if all(required) else "BLOCKED"
    result = {
        "schemaVersion": "agent-rag-v22-real-model-chain-gate-v1",
        "status": status,
        "modelQuality": model_quality,
        "runtimeCorrectness": runtime_correctness,
        "legacyRepositoryDebt": legacy_repository_debt,
        "checks": checks,
        "tokens": tokens(status, checks),
        "boundaries": boundaries(model_quality, legacy_repository_debt),
    }
    write_json(OUT, result)
    for token in result["tokens"]:
        print(token)
    return 0 if status == "PASS" else 2


def tokens(status: str, checks: dict[str, bool]) -> list[str]:
    values = []
    if checks["realEmbeddingPass"]:
        values.append("AGENT_RAG_V22_REAL_EMBEDDING_PASS")
    if checks["realRerankerRuntimePass"]:
        values.append("AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS")
    if checks["realRerankerQualityImproved"]:
        values.append("AGENT_RAG_V22_REAL_RERANKER_PASS")
    if checks["realLlmQualityVerified"]:
        values.append("AGENT_RAG_V22_REAL_LLM_PASS")
    if checks["gpuResidencyPass"]:
        values.append("AGENT_RAG_V22_GPU_8GB_STABILITY_PASS")
    if checks["javaE2ePass"]:
        values.append("AGENT_RAG_V22_REAL_MODEL_E2E_PASS")
    if status == "PASS":
        values.extend(["AGENT_RAG_V22_GROUNDED_MODEL_CHAIN_PASS", "AGENT_RAG_V22_REAL_MODEL_CHAIN_PASS"])
    else:
        values.append("AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED")
    return values


def boundaries(model_quality: dict[str, bool], legacy_repository_debt: dict[str, Any]) -> list[str]:
    values = [
        "MODEL_RERANKER_VERIFIED"
        if model_quality["realRerankerQualityImproved"]
        else ("MODEL_RERANKER_VERIFIED_OPTIONAL" if model_quality["realRerankerQualityParityOnly"] else "MODEL_RERANKER_NOT_VERIFIED"),
        "REAL_LLM_QUALITY_VERIFIED" if model_quality["realLlmQualityVerified"] else "REAL_LLM_QUALITY_NOT_VERIFIED",
        "MODEL_FINE_TUNING_NOT_VERIFIED",
        "MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED",
        "DISTRIBUTED_VECTOR_DATABASE_NOT_VERIFIED",
        "HIGH_AVAILABILITY_NOT_VERIFIED",
        "PRODUCTION_CONCURRENCY_NOT_VERIFIED",
        "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
        "NO_PUSH",
        "NO_TAG",
        "NO_RELEASE",
    ]
    debt = legacy_repository_debt.get("adminLegacyLintDebt") or 0
    if debt:
        values.extend([f"ADMIN_LEGACY_LINT_DEBT_{debt}", "ADMIN_FULL_LINT_NOT_CLEAN"])
    return values


def asset_manifest_exists() -> bool:
    manifest = os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", "")
    return bool(manifest) and Path(manifest).exists()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
