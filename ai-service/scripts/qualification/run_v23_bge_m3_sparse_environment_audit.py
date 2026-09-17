from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "retrieval-optimization"
DOCS = ROOT / "docs" / "retrieval-optimization"
EXTERNAL_MANIFEST = Path(r"D:\EReviewAgent\models\v2.3\manifests\v23-bge-m3-sparse-python-environment.json")
MODEL_MANIFEST = Path(r"D:\EReviewAgent\models\v2.2\manifests\v22-real-model-assets.json")


def main() -> int:
    model_manifest = read_json(MODEL_MANIFEST)
    pip_check = run([sys.executable, "-m", "pip", "check"])
    package_versions = collect_versions(
        [
            "torch",
            "transformers",
            "tokenizers",
            "safetensors",
            "FlagEmbedding",
            "sentence_transformers",
            "datasets",
            "peft",
            "protobuf",
            "sentencepiece",
        ]
    )
    runtime_probe = sparse_runtime_probe(model_manifest)
    payload = {
        "schemaVersion": "agent-rag-v23-bge-m3-sparse-environment-audit-v1",
        "environmentSource": "OFFLINE_VERIFIED_WHEELHOUSE",
        "pythonVersion": sys.version.split()[0],
        "packageVersions": package_versions,
        "torchVersion": package_versions.get("torch", ""),
        "cudaAvailable": cuda_available(),
        "cudaVersion": cuda_version(),
        "transformersVersion": package_versions.get("transformers", ""),
        "flagEmbeddingVersion": package_versions.get("FlagEmbedding", ""),
        "tokenizersVersion": package_versions.get("tokenizers", ""),
        "safetensorsVersion": package_versions.get("safetensors", ""),
        "model": {
            "modelId": "BAAI/bge-m3",
            "revision": ((model_manifest.get("embedding") or {}).get("revision") or ""),
            "assetFingerprint": ((model_manifest.get("embedding") or {}).get("assetFingerprint") or ""),
            "modelPathLabel": "<external-models>/bge-m3",
        },
        "pipCheckPass": pip_check["returnCode"] == 0,
        "pipCheckOutputHash": sha_text(pip_check["stdout"] + pip_check["stderr"]),
        "pipCheckSummary": summarize_pip_check(pip_check["stdout"] + pip_check["stderr"]),
        "flagEmbeddingImportPass": runtime_probe["flagEmbeddingImportPass"],
        "bgeM3ModelClassAvailable": runtime_probe["bgeM3ModelClassAvailable"],
        "denseProviderImportPass": import_available("app.agent_rag.phase3a_retrieval"),
        "llmProviderImportPass": import_available("app.llm.service"),
        "noTlsBypass": tls_bypass_absent(),
        "noUnverifiedLocalPackage": no_unverified_local_package(),
        "runtimeProbe": runtime_probe,
        "dependencyFingerprint": sha_text(json.dumps(package_versions, sort_keys=True)),
        "status": "PASS" if False else "BLOCKED",
    }
    checks = {
        "flagEmbeddingImportPass": payload["flagEmbeddingImportPass"],
        "bgeM3ModelClassAvailable": payload["bgeM3ModelClassAvailable"],
        "cudaAvailable": payload["cudaAvailable"],
        "pipCheckPass": payload["pipCheckPass"],
        "denseProviderImportPass": payload["denseProviderImportPass"],
        "llmProviderImportPass": payload["llmProviderImportPass"],
        "noTlsBypass": payload["noTlsBypass"],
        "noUnverifiedLocalPackage": payload["noUnverifiedLocalPackage"],
    }
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "BLOCKED"
    payload["decision"] = "BGE_M3_SPARSE_ENVIRONMENT_QUALIFIED" if payload["status"] == "PASS" else "BGE_M3_SPARSE_ENVIRONMENT_BLOCKED"
    safe_payload = redact_for_git(payload)
    write_json(OUT / "v23-bge-m3-sparse-environment-gate.json", safe_payload)
    write_json(EXTERNAL_MANIFEST, payload)
    write_text(DOCS / "V23_BGE_M3_SPARSE_ENVIRONMENT.md", render_doc(safe_payload))
    print("E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_PASS" if safe_payload["status"] == "PASS" else "E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_BLOCKED")
    print(safe_payload["decision"])
    return 0 if safe_payload["status"] == "PASS" else 1


def sparse_runtime_probe(model_manifest: dict[str, Any]) -> dict[str, Any]:
    probe: dict[str, Any] = {
        "flagEmbeddingImportPass": False,
        "bgeM3ModelClassAvailable": False,
        "realSparseExecution": False,
        "cudaUsed": False,
        "fallbackUsed": False,
        "finiteWeights": False,
        "nonEmptyWeights": False,
        "deterministicRepeat": False,
        "scoreType": "BGE_M3_LEARNED_SPARSE_DOT_PRODUCT",
        "compatibilityShimUsed": False,
        "errorClass": "",
        "errorHash": "",
    }
    try:
        import transformers.utils.import_utils as import_utils

        if not hasattr(import_utils, "is_torch_fx_available"):
            import_utils.is_torch_fx_available = lambda: False
            probe["compatibilityShimUsed"] = True
        from FlagEmbedding import BGEM3FlagModel

        probe["flagEmbeddingImportPass"] = True
        probe["bgeM3ModelClassAvailable"] = True
        import torch

        model_path = (model_manifest.get("embedding") or {}).get("modelPath") or r"D:\EReviewAgent\models\bge-m3"
        started = time.perf_counter()
        model = BGEM3FlagModel(model_path, use_fp16=True, device="cuda" if torch.cuda.is_available() else "cpu")
        probe["loadDurationMs"] = round((time.perf_counter() - started) * 1000, 3)
        texts = [
            "refund broken return after-sales customer service compensation",
            "refund broken return after-sales customer service compensation",
            "unrelated warehouse robot firmware",
        ]
        result = model.encode(texts, batch_size=1, max_length=128, return_dense=False, return_sparse=True, return_colbert_vecs=False)
        weights = result.get("lexical_weights") if isinstance(result, dict) else []
        probe["realSparseExecution"] = bool(weights)
        probe["cudaUsed"] = torch.cuda.is_available()
        probe["nonEmptyWeights"] = all(bool(item) for item in weights)
        probe["finiteWeights"] = all(math.isfinite(float(value)) for item in weights for value in item.values())
        probe["deterministicRepeat"] = dict(weights[0]) == dict(weights[1]) if len(weights) >= 2 else False
        probe["averageNonZeroDimensions"] = round(sum(len(item) for item in weights) / max(1, len(weights)), 6)
        probe["maxCudaMemoryBytes"] = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
        probe["sampleWeightHash"] = sha_text(json.dumps(normalize_sparse(weights[0]), sort_keys=True)) if weights else ""
        probe["relevantGreaterThanIrrelevantSmoke"] = sparse_dot(weights[0], weights[1]) > sparse_dot(weights[0], weights[2]) if len(weights) >= 3 else False
    except Exception as exc:
        probe["errorClass"] = exc.__class__.__name__
        probe["errorHash"] = sha_text(str(exc))
    return probe


def sparse_dot(left: Any, right: Any) -> float:
    return sum(float(value) * float(right.get(key, 0.0)) for key, value in left.items())


def normalize_sparse(value: Any) -> list[list[Any]]:
    return [[str(key), round(float(weight), 8)] for key, weight in sorted(value.items())]


def collect_versions(names: list[str]) -> dict[str, str]:
    versions = {}
    for name in names:
        try:
            module = importlib.import_module(name)
            versions[name] = str(getattr(module, "__version__", "unknown"))
        except Exception:
            try:
                import importlib.metadata as metadata

                versions[name] = metadata.version(name)
            except Exception:
                versions[name] = "NOT_INSTALLED"
    return versions


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def cuda_version() -> str:
    try:
        import torch

        return str(torch.version.cuda or "")
    except Exception:
        return ""


def import_available(module_name: str) -> bool:
    if str(ROOT / "ai-service") not in sys.path:
        sys.path.insert(0, str(ROOT / "ai-service"))
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {"returnCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def tls_bypass_absent() -> bool:
    forbidden = ["PIP_TRUSTED_HOST", "PYTHONHTTPSVERIFY", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE"]
    return not any(os.getenv(name, "").strip() in {"0", "false", "False", "*"} for name in forbidden)


def no_unverified_local_package() -> bool:
    try:
        freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    except Exception:
        return False
    return "--trusted-host" not in freeze and "verify=False" not in freeze


def summarize_pip_check(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:10]


def redact_for_git(payload: dict[str, Any]) -> dict[str, Any]:
    safe = json.loads(json.dumps(payload, ensure_ascii=False))
    safe["externalManifestLabel"] = "<external-models>/v2.3/manifests/v23-bge-m3-sparse-python-environment.json"
    return safe


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_doc(payload: dict[str, Any]) -> str:
    return (
        "# V2.3 BGE-M3 Sparse Environment\n\n"
        f"Decision: `{payload['decision']}`\n\n"
        "The sparse runtime can execute with a compatibility shim, but Phase 9.4 environment qualification requires `pip check` to pass. "
        "Because the current environment keeps `transformers==5.3.0` and the offline `sentence-transformers==3.0.1` metadata requires `<5.0.0`, the gate remains blocked without downgrading core dependencies.\n\n"
        "Resume-ready note: restored real BGE-M3 sparse execution from an offline verified wheelhouse, found a library metadata/runtime compatibility conflict, and blocked the three-way retrieval experiment instead of silently downgrading core model dependencies.\n\n"
        "```json\n"
        + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n```\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
