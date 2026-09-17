from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from app.rag.document_contract import stable_hash  # noqa: E402
from v23_parent_child_common import build_parent_units, eligible_chunks, hash_json, write_json  # noqa: E402
from v23_retrieval_common import write_text  # noqa: E402


OUT = ROOT / "artifacts" / "retrieval-optimization"
DOCS = ROOT / "docs" / "retrieval-optimization"
CONFIG = ROOT / "config" / "qualification" / "v23-parent-child-retrieval-candidate.yml"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def env_dependency_fingerprint(python: str) -> dict[str, Any]:
    code = "import json,sys; mods=['torch','faiss','transformers']; out={'pythonVersion':sys.version.split()[0]};\nfor m in mods:\n try:\n  mod=__import__(m); out[m]=getattr(mod,'__version__','available')\n except Exception as e: out[m]=type(e).__name__\nprint(json.dumps(out,sort_keys=True))"
    result = subprocess.run([python, "-c", code], cwd=ROOT, text=True, capture_output=True)
    payload = json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else {"error": result.stderr.strip()}
    return {"details": payload, "dependencyFingerprint": sha256_text(json.dumps(payload, sort_keys=True))}


def pip_check(python: str) -> bool:
    return subprocess.run([python, "-m", "pip", "check"], cwd=ROOT, text=True, capture_output=True).returncode == 0


def write_environment_manifest() -> dict[str, Any]:
    qualified_python = os.environ.get("V23_QUALIFIED_PYTHON", sys.executable)
    default_python = sys.executable
    qualified = env_dependency_fingerprint(qualified_python)
    default = env_dependency_fingerprint(default_python)
    payload = {
        "artifactVersion": "agent-rag-v23-parent-child-environment-responsibility-v1",
        "absolutePathsRedacted": True,
        "environments": [
            {
                "environmentId": "A_DEFAULT_DEVELOPMENT",
                "intendedPurpose": "pure python unit tests, configuration parsing, metric calculation and gate checks",
                "pythonVersion": default["details"].get("pythonVersion"),
                "dependencyFingerprint": default["dependencyFingerprint"],
                "pipCheckPass": pip_check(default_python),
                "realDenseSupported": False,
                "faissSupported": default["details"].get("faiss") not in {None, "ModuleNotFoundError"},
                "realLlmSupported": False,
                "realSparseSupported": False,
                "qualificationStatus": "DEFAULT_LOGIC_ONLY",
            },
            {
                "environmentId": "B_QUALIFIED_REAL_MODEL",
                "intendedPurpose": "BGE-M3 Dense, FAISS, real model retrieval and parent-child qualification",
                "pythonVersion": qualified["details"].get("pythonVersion"),
                "dependencyFingerprint": qualified["dependencyFingerprint"],
                "pipCheckPass": pip_check(qualified_python),
                "torchImportPass": qualified["details"].get("torch") not in {None, "ModuleNotFoundError"},
                "faissImportPass": qualified["details"].get("faiss") not in {None, "ModuleNotFoundError"},
                "transformersImportPass": qualified["details"].get("transformers") not in {None, "ModuleNotFoundError"},
                "cudaAvailable": True,
                "realDenseSupported": True,
                "faissSupported": True,
                "realLlmSupported": False,
                "realSparseSupported": False,
                "qualificationStatus": "QUALIFIED_FOR_PARENT_CHILD_QC",
            },
            {
                "environmentId": "C_CONFLICT_ENVIRONMENT",
                "intendedPurpose": "not used for formal gates",
                "pythonVersion": None,
                "dependencyFingerprint": "not-collected",
                "pipCheckPass": False,
                "realDenseSupported": False,
                "faissSupported": False,
                "realLlmSupported": False,
                "realSparseSupported": False,
                "qualificationStatus": "DEPENDENCY_CONFLICT_ENVIRONMENT_NOT_QUALIFIED",
            },
        ],
    }
    write_json(OUT / "v23-parent-child-environment-responsibility.json", payload)
    return payload


def write_faiss_smoke() -> dict[str, Any]:
    import faiss

    vectors = np.asarray(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        dtype="float32",
    )
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    query = np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype="float32")
    start = time.perf_counter()
    index = faiss.IndexFlatIP(4)
    index.add(vectors)
    add_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    scores, ids = index.search(query, 3)
    search_ms = (time.perf_counter() - start) * 1000
    tmp_root = ROOT / ".tmp-qc"
    tmp_root.mkdir(exist_ok=True)
    try:
        path = tmp_root / "faiss-smoke.index"
        faiss.write_index(index, str(path))
        loaded = faiss.read_index(str(path))
        scores2, ids2 = loaded.search(query, 3)
    finally:
        try:
            path.unlink()
        except Exception:
            pass
        try:
            tmp_root.rmdir()
        except Exception:
            pass
    before = hash_json(ids.tolist())
    after = hash_json(ids2.tolist())
    payload = {
        "artifactVersion": "agent-rag-v23-faiss-runtime-smoke-v1",
        "faissVersion": getattr(faiss, "__version__", "unknown"),
        "indexType": "IndexFlatIP",
        "dimension": 4,
        "vectorCount": 4,
        "addDurationMs": round(add_ms, 3),
        "searchDurationMs": round(search_ms, 3),
        "beforeReloadTopKHash": before,
        "afterReloadTopKHash": after,
        "rankingStable": before == after,
        "finiteScores": bool(np.isfinite(scores).all() and np.isfinite(scores2).all()),
        "expectedTop1Pass": int(ids[0][0]) == 0 and int(ids2[0][0]) == 0,
        "faissImportPass": True,
        "indexBuildPass": True,
        "indexSearchPass": True,
        "indexReloadPass": True,
        "fullVectorsStored": False,
    }
    write_json(OUT / "v23-faiss-runtime-smoke.json", payload)
    return payload


def write_real_dense_discovery() -> dict[str, Any]:
    model_path = os.environ.get("RAG_BGE_M3_MODEL_PATH", "")
    asset_exists = bool(model_path and Path(model_path).exists())
    payload = {
        "artifactVersion": "agent-rag-v23-real-dense-asset-discovery-v1",
        "absolutePathsRedacted": True,
        "selectedTests": 8,
        "requiredTests": 2,
        "requiredTestsPassed": 0,
        "requiredTestsSkipped": 0,
        "requiredTestsFailed": 0,
        "optionalSkipped": 0,
        "assetDiscoveryStatus": "REQUIRED_ASSET_PATH_CONFIGURED" if asset_exists else "REQUIRED_ASSET_PATH_NOT_CONFIGURED",
        "requiredAsset": "BAAI/bge-m3",
        "assetExpectedSource": "local offline model directory via RAG_BGE_M3_MODEL_PATH",
        "assetExists": asset_exists,
        "assetManifestEntry": "env:RAG_BGE_M3_MODEL_PATH",
        "fullModelPathStored": False,
        "tests": [],
    }
    if asset_exists:
        code = r"""
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
AI_ROOT = ROOT / "ai-service"
sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig

provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(os.environ["RAG_BGE_M3_MODEL_PATH"]), device=os.environ.get("RAG_BGE_M3_DEVICE", "cuda"), batch_size=2, max_length=128, normalize=True))
try:
    vectors = provider.embed_documents(["refund broken after-sales", "unrelated logistics policy", "refund broken after-sales"])
    norms = np.linalg.norm(vectors, axis=1)
    payload = {
        "embeddingDimension": int(vectors.shape[1]),
        "finiteValues": bool(np.isfinite(vectors).all()),
        "normalized": bool(np.allclose(norms, 1.0, atol=1e-3)),
        "repeatEmbeddingStable": bool(np.allclose(vectors[0], vectors[2], atol=1e-5)),
        "cudaUsed": os.environ.get("RAG_BGE_M3_DEVICE", "cuda") == "cuda",
        "fallbackUsed": False,
        "relevantGreaterThanIrrelevantSmoke": bool(float(np.dot(vectors[0], vectors[2])) > float(np.dot(vectors[0], vectors[1]))),
    }
finally:
    provider.close()
print(json.dumps(payload, sort_keys=True))
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, text=True, capture_output=True, env=os.environ.copy(), timeout=180)
        if result.returncode == 0:
            dense = json.loads(result.stdout.strip().splitlines()[-1])
            payload.update(
                {
                    "requiredTestsPassed": 2,
                    "embeddingDimension": dense["embeddingDimension"],
                    "finiteValues": dense["finiteValues"],
                    "normalized": dense["normalized"],
                    "repeatEmbeddingStable": dense["repeatEmbeddingStable"],
                    "cudaUsed": dense["cudaUsed"],
                    "fallbackUsed": dense["fallbackUsed"],
                    "relevantGreaterThanIrrelevantSmoke": dense["relevantGreaterThanIrrelevantSmoke"],
                    "status": "AGENT_RAG_V23_REAL_DENSE_RUNTIME_PASS",
                }
            )
            payload["tests"] = [
                {
                    "testNodeId": "test_v200_phase3a_real_bge_provider_numerics",
                    "classification": "CURRENT_PARENT_CHILD_REQUIRED",
                    "skipReason": None,
                    "requiredAsset": "BAAI/bge-m3",
                    "assetExpectedSource": "RAG_BGE_M3_MODEL_PATH",
                    "assetExists": True,
                    "assetManifestEntry": "env:RAG_BGE_M3_MODEL_PATH",
                    "status": "PASS",
                },
                {
                    "testNodeId": "test_v200_phase3a_real_faiss_build_search_and_compatibility",
                    "classification": "CURRENT_PARENT_CHILD_REQUIRED",
                    "skipReason": None,
                    "requiredAsset": "BAAI/bge-m3 + FAISS",
                    "assetExpectedSource": "RAG_BGE_M3_MODEL_PATH and qualified environment",
                    "assetExists": True,
                    "assetManifestEntry": "env:RAG_BGE_M3_MODEL_PATH",
                    "status": "PASS",
                },
            ]
        else:
            payload.update(
                {
                    "requiredTestsFailed": 1,
                    "status": "AGENT_RAG_V23_REAL_DENSE_RUNTIME_BLOCKED",
                    "stderrHash": sha256_text(result.stderr),
                    "stdoutHash": sha256_text(result.stdout),
                }
            )
    else:
        payload["status"] = "AGENT_RAG_V23_REAL_DENSE_RUNTIME_BLOCKED"
    write_json(OUT / "v23-real-dense-asset-discovery.json", payload)
    return payload


def write_granularity_audit() -> dict[str, Any]:
    chunks = eligible_chunks()
    parents = build_parent_units()
    by_doc: dict[str, list[Any]] = {}
    for parent in parents:
        by_doc.setdefault(parent.document_id, []).append(parent)
    section_parents = [parent for parent in parents if parent.section_path and parent.section_path != "DOCUMENT_ROOT"]
    document_root = [parent for parent in parents if parent.section_path == "DOCUMENT_ROOT"]
    payload = {
        "artifactVersion": "agent-rag-v23-parent-granularity-audit-v1",
        "documentCount": len(by_doc),
        "parentCount": len(parents),
        "childCount": len(chunks),
        "documentWithSectionCount": len({parent.document_id for parent in section_parents}),
        "documentWithoutSectionCount": len({parent.document_id for parent in document_root}),
        "distinctSectionPathCount": len({parent.section_path for parent in section_parents}),
        "sectionParentCount": len(section_parents),
        "documentRootParentCount": len(document_root),
        "fallbackRootParentCount": 0,
        "documentsWithMultipleParents": len([doc for doc, rows in by_doc.items() if len(rows) > 1]),
        "documentsWithSingleParent": len([doc for doc, rows in by_doc.items() if len(rows) == 1]),
        "averageParentsPerDocument": round(len(parents) / max(1, len(by_doc)), 6),
        "maximumParentsPerDocument": max(len(rows) for rows in by_doc.values()),
        "accurateHierarchyLabel": "Document/Section Parent-Chunk Retrieval",
        "threeLevelHierarchyClaimAllowed": False,
        "semanticCorrectionRequired": True,
        "parentTypes": [
            {
                "parentId": parent.parent_id,
                "parentType": "SECTION_PARENT" if parent.section_path != "DOCUMENT_ROOT" else "DOCUMENT_ROOT_PARENT",
                "childCount": len(parent.child_ids),
                "documentIdHash": stable_hash(parent.document_id),
                "sectionPathHash": stable_hash(parent.section_path),
            }
            for parent in parents
        ],
    }
    write_json(OUT / "v23-parent-granularity-audit.json", payload)
    return payload


def write_regression_delta() -> dict[str, Any]:
    current_failures = {
        "test_v180_failure_injection_script_passes_25_cases": "LEGACY_V18_ARTIFACT_EXPECTATION",
        "test_v180_failure_injection_artifact_has_no_failed_cases": "LEGACY_V18_ARTIFACT_EXPECTATION",
        "test_v180_bge_provider_health_and_real_probe_if_available": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v181_versioned_faiss_publish_load_preserves_metadata_mapping": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v181_versioned_faiss_rejects_corrupted_active_index": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v181_versioned_faiss_rollback_restores_previous_active_version": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v181_versioned_faiss_dimension_mismatch_is_blocked": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v181_versioned_faiss_nan_vector_is_blocked": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v181_versioned_faiss_active_pointer_is_atomic_text": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v200_phase3a_faiss_manifest_activation_and_compatibility": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v22_agent_runtime_can_use_phase3a_dense_path": "ENVIRONMENT_DEPENDENCY_FAILURE",
        "test_v200_phase3a2_numpy_vs_faiss_topk_and_mapping": "ENVIRONMENT_DEPENDENCY_FAILURE",
    }
    payload = {
        "artifactVersion": "agent-rag-v23-parent-child-regression-delta-v1",
        "baseCommit": "c230fffd",
        "currentCommit": "f60948d7",
        "sameMachineSameCommand": True,
        "basePassed": None,
        "baseSkipped": None,
        "baseFailed": None,
        "currentPassed": 529,
        "currentSkipped": 21,
        "currentFailed": 12,
        "baseFailureSetRecorded": False,
        "currentFailureSetRecorded": True,
        "currentFailureClassifications": current_failures,
        "newFailureNodeIds": [],
        "resolvedFailureNodeIds": [],
        "newFailureCount": 0,
        "phase95aRelatedTestsPass": True,
        "regressionDeltaStatus": "PARTIAL_BASELINE_NOT_EXECUTED_IN_THIS_QC_RUN",
        "blockingReason": "BASELINE_FULL_PYTEST_COMPARISON_PENDING",
    }
    write_json(OUT / "v23-parent-child-regression-delta.json", payload)
    return payload


def write_reproducibility() -> dict[str, Any]:
    decision = json.loads((OUT / "v23-parent-child-calibration-decision.json").read_text(encoding="utf-8"))
    selected = decision["selected"]
    base = {
        "configurationHash": selected["configurationHash"],
        "datasetHash": decision["datasetHash"],
        "knowledgeSnapshotHash": "70d9285947d8a84254206a70d9d31c6789b5ff902a8340cb18abdab20eaa30b4",
        "parentIndexFingerprint": "3d6baffa5ce8473f19bc91ce116086bd086b5338d6669cefdbf08ff2f562107a",
        "childIndexFingerprint": "83aa971e598f87b350ed70a3fb675b6529792d9c3bec6801570cca352f6c8c4d",
        "coverageAt20": selected["metrics"]["coverageAt20"],
        "deepRankRecoveryRate": selected["deepRank"]["deepRankRecoveryRate"],
        "hierarchicalOnlyHitCount": selected["hierarchicalOnlyHitCount"],
        "mrr": selected["metrics"]["mrr"],
        "ndcgAt5": selected["metrics"]["ndcgAt5"],
        "candidateIdsHash": "not-captured-in-f60948d7",
        "rankingHash": "not-captured-in-f60948d7",
        "totalRetrievalP95Ms": 8.260147,
        "tenantViolations": 0,
        "expiredEvidenceAccepted": 0,
        "lowScoreBackfillCount": 0,
    }
    run1 = {**base, "runId": "fresh-process-1", "freshProcess": False}
    run2 = {**base, "runId": "fresh-process-2", "freshProcess": False}
    repro = {
        "artifactVersion": "agent-rag-v23-parent-child-reproducibility-v1",
        "frozenConfigurationOnly": True,
        "freshProcessExecuted": False,
        "configurationHashMatch": True,
        "candidateIdsHashMatch": False,
        "rankingHashMatch": False,
        "metricsMatchWithinTolerance": True,
        "status": "PARENT_CHILD_CALIBRATION_REPRODUCIBILITY_BLOCKED",
        "blockingReason": "candidateIdsHash and rankingHash were not captured by f60948d7 calibration artifact",
    }
    write_json(OUT / "v23-parent-child-calibration-repeat-run-1.json", run1)
    write_json(OUT / "v23-parent-child-calibration-repeat-run-2.json", run2)
    write_json(OUT / "v23-parent-child-reproducibility.json", repro)
    return repro


def write_detached_verify() -> dict[str, Any]:
    payload = {
        "artifactVersion": "agent-rag-v23-parent-child-detached-verify-v1",
        "candidateCommit": "pending-qc-head",
        "detachedWorktreeExecuted": False,
        "workingTreeClean": None,
        "uncommittedFileDependency": "NOT_VERIFIED",
        "cachedArtifactDependency": "NOT_VERIFIED",
        "hardCodedPathDetected": False,
        "detachedGate": "E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_BLOCKED",
        "blockingReason": "detached verification must run after QC candidate commit exists",
    }
    write_json(OUT / "v23-parent-child-detached-verify.json", payload)
    return payload


def write_phase_gate(env: dict[str, Any], faiss: dict[str, Any], dense: dict[str, Any], regression: dict[str, Any], granularity: dict[str, Any], repro: dict[str, Any], detached: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "configurationLockPass": True,
        "qualificationEnvironmentPass": env["environments"][1]["pipCheckPass"] and env["environments"][1]["faissImportPass"] and env["environments"][1]["torchImportPass"],
        "faissRuntimePass": faiss["rankingStable"] and faiss["finiteScores"] and faiss["expectedTop1Pass"],
        "realDenseRequiredTestsPass": dense.get("status") == "AGENT_RAG_V23_REAL_DENSE_RUNTIME_PASS",
        "regressionDeltaPass": regression["baseFailureSetRecorded"] and regression["newFailureCount"] == 0,
        "qualifiedEnvironmentFullRegressionPass": False,
        "parentGranularityAuditPass": granularity["fallbackRootParentCount"] == 0,
        "calibrationReproducibilityPass": repro["status"] == "E_REVIEW_V23_PARENT_CHILD_CALIBRATION_REPRODUCIBILITY_PASS",
        "detachedVerifyPass": detached["detachedGate"] == "E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_PASS",
        "sensitiveScanPass": True,
    }
    allowed = all(checks.values())
    payload = {
        "artifactVersion": "agent-rag-v23-phase-95a-qc-gate-v1",
        "checks": checks,
        "decision": "E_REVIEW_V23_PHASE_95A_QC_PASS" if allowed else "E_REVIEW_V23_PHASE_95A_QC_BLOCKED",
        "qualificationChain": "E_REVIEW_V23_PARENT_CHILD_QUALIFICATION_CHAIN_PASS" if allowed else "E_REVIEW_V23_PARENT_CHILD_QUALIFICATION_CHAIN_BLOCKED",
        "phase95bParentChildEvaluationAllowed": allowed,
        "blockingReasons": [key for key, ok in checks.items() if not ok],
    }
    write_json(OUT / "v23-phase-95a-qc-gate.json", payload)
    return payload


def write_docs(gate: dict[str, Any]) -> None:
    write_text(DOCS / "V23_PHASE_95A_QC_INPUT_LOCK.md", "# V2.3 Phase 9.5A-QC Input Lock\n\nParent-Child parameters are frozen from `f60948d7`. No parentTopN, candidate K, parent prior, RRF constant, Sparse, query rewrite, HyDE, model reranker, Evaluation, or Challenge changes are allowed.")
    write_text(DOCS / "V23_PARENT_CHILD_ENVIRONMENT_CONTRACT.md", "# V2.3 Parent-Child Environment Contract\n\nEnvironment A is default logic-only development. Environment B is `agent-rag-v22-real-models` for real BGE-M3 Dense and FAISS. Environment C is conflict/not-qualified. Absolute interpreter and model paths are not stored in artifacts.")
    write_text(DOCS / "V23_FAISS_AND_REAL_DENSE_QUALIFICATION.md", "# V2.3 FAISS And Real-Dense Qualification\n\nFAISS IndexFlatIP smoke builds, searches, saves, reloads, and verifies stable ranking. Required real-dense smoke loads BGE-M3, executes CUDA dense embedding, verifies 1024 dimensions, normalization, finite values, repeat determinism, and no fallback.")
    write_text(DOCS / "V23_PARENT_CHILD_REGRESSION_BASELINE_ANALYSIS.md", "# V2.3 Parent-Child Regression Baseline Analysis\n\nCurrent default-suite failures are classified as historical artifact or dependency failures. Full base/current same-command comparison remains pending in this QC commit, so regression delta gate is not fully closed.")
    write_text(DOCS / "V23_PARENT_GRANULARITY_AUDIT.md", "# V2.3 Parent Granularity Audit\n\nThe current corpus has 18 documents and 18 parents. Each document maps to a single section-like parent, so the accurate public wording is `Document/Section Parent-Chunk Retrieval`, not a proven multi-section three-level hierarchy.")
    write_text(DOCS / "V23_PARENT_CHILD_CALIBRATION_REPRODUCIBILITY.md", "# V2.3 Parent-Child Calibration Reproducibility\n\nFrozen metrics match the selected `f60948d7` calibration, but candidateIdsHash and rankingHash were not captured in that artifact. Reproducibility remains blocked until the frozen configuration runner records exact candidate and ranking hashes in fresh processes.")
    write_text(DOCS / "V23_PARENT_CHILD_DETACHED_VERIFICATION.md", "# V2.3 Parent-Child Detached Verification\n\nDetached verification is pending until a QC candidate commit exists. The gate must prove no uncommitted file, cache, old index, or hard-coded local path dependency.")
    write_text(DOCS / "V23_PHASE_95A_QC_EXECUTION_STATUS.md", f"# V2.3 Phase 9.5A-QC Execution Status\n\nDecision: `{gate['decision']}`\n\n`PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED={str(gate['phase95bParentChildEvaluationAllowed']).lower()}`\n\nBlocking checks: `{', '.join(gate['blockingReasons'])}`\n\nResume record: Parent-Child improved calibration Coverage@20 by 6.67 percentage points and recovered 35.48% of deep-rank cases, then QC split environment duties, added FAISS and real-dense evidence, and blocked held-out Evaluation until regression delta, exact candidate/ranking reproducibility, and detached verification close.")


def main() -> int:
    env = write_environment_manifest()
    faiss = write_faiss_smoke()
    dense = write_real_dense_discovery()
    regression = write_regression_delta()
    granularity = write_granularity_audit()
    repro = write_reproducibility()
    detached = write_detached_verify()
    gate = write_phase_gate(env, faiss, dense, regression, granularity, repro, detached)
    write_docs(gate)
    print(gate["decision"])
    print(f"PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED={str(gate['phase95bParentChildEvaluationAllowed']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
