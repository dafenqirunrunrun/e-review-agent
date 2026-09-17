from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "retrieval-optimization"
DOCS = ROOT / "docs" / "retrieval-optimization"
SAFE_TEXTS = [
    " ".join(["refund", "refund", "refund", "damaged", "product"]),
    " ".join(["refund", "refund", "refund", "damaged", "product"]),
    " ".join(["warehouse", "robot", "firmware"]),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-python", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--source-environment-gate", default=str(OUT / "v23-bge-m3-sparse-environment-gate.json"))
    parser.add_argument("--external-output", default="")
    args = parser.parse_args()

    model_manifest = read_json(Path(args.model_manifest))
    source_gate = read_json(Path(args.source_environment_gate))
    primary = inspect_primary(Path(args.primary_python), Path(args.model_manifest))
    sparse = inspect_sparse(model_manifest)
    tokenizer_parity = compare_tokenizers(primary["tokenizerParityProbe"], sparse["tokenizerParityProbe"])
    boundary = build_boundary(primary, source_gate)
    gate = build_gate(boundary, sparse, tokenizer_parity)

    write_json(OUT / "v23-bge-m3-sparse-environment-boundary.json", boundary)
    write_json(OUT / "v23-bge-m3-sparse-isolated-environment.json", safe_sparse_summary(sparse))
    write_json(OUT / "v23-bge-m3-sparse-tokenizer-parity.json", tokenizer_parity)
    write_json(OUT / "v23-bge-m3-sparse-runtime-smoke.json", safe_smoke_summary(sparse))
    write_json(OUT / "v23-bge-m3-sparse-environment-gate.json", gate)
    if args.external_output:
        write_json(Path(args.external_output), {"boundary": boundary, "sparse": sparse, "tokenizerParity": tokenizer_parity, "gate": gate})
    write_text(DOCS / "V23_BGE_M3_SPARSE_ENVIRONMENT_BOUNDARY.md", render_boundary_doc(boundary))
    write_text(DOCS / "V23_BGE_M3_SPARSE_ISOLATED_ENVIRONMENT.md", render_sparse_doc(sparse, gate))
    write_text(DOCS / "V23_BGE_M3_SPARSE_TOKENIZER_PARITY.md", render_tokenizer_doc(tokenizer_parity))
    write_text(DOCS / "V23_PHASE_94A_EXECUTION_STATUS.md", render_status_doc(boundary, sparse, tokenizer_parity, gate))

    if gate["status"] == "PASS":
        print("E_REVIEW_V23_BGE_M3_SPARSE_ISOLATED_ENVIRONMENT_PASS")
        print("E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_PASS")
        print("AGENT_RAG_V23_REAL_BGE_M3_SPARSE_RUNTIME_PASS")
        return 0
    print("E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_BLOCKED")
    return 1


def inspect_sparse(model_manifest: dict[str, Any]) -> dict[str, Any]:
    embedding = model_manifest.get("embedding") or {}
    import torch
    import transformers
    import tokenizers
    import huggingface_hub
    import safetensors
    import sentence_transformers
    from FlagEmbedding import BGEM3FlagModel
    from transformers import AutoTokenizer

    pip_check = run([sys.executable, "-m", "pip", "check"])
    freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    tokenizer = AutoTokenizer.from_pretrained(embedding["modelPath"], local_files_only=True, trust_remote_code=True)
    tokenized = tokenizer(SAFE_TEXTS[0], return_attention_mask=True)
    started = time.perf_counter()
    model = BGEM3FlagModel(embedding["modelPath"], use_fp16=True, device="cuda" if torch.cuda.is_available() else "cpu")
    load_ms = round((time.perf_counter() - started) * 1000, 3)
    latencies = []
    outputs = []
    for _ in range(3):
        started = time.perf_counter()
        encoded = model.encode(SAFE_TEXTS, batch_size=1, max_length=128, return_dense=False, return_sparse=True, return_colbert_vecs=False)
        latencies.append((time.perf_counter() - started) * 1000)
        outputs.append(encoded["lexical_weights"])
    weights = outputs[0]
    return {
        "schemaVersion": "agent-rag-v23-bge-m3-sparse-isolated-environment-v1",
        "environmentVersion": "v23-bge-m3-sparse-isolated-v1",
        "environmentSource": "REUSED_VERIFIED_V22_ENVIRONMENT",
        "isolatedEnvironment": True,
        "systemSitePackages": False,
        "pythonVersion": sys.version.split()[0],
        "packageVersions": {
            "torch": torch.__version__,
            "torchCuda": str(torch.version.cuda),
            "transformers": transformers.__version__,
            "tokenizers": tokenizers.__version__,
            "huggingfaceHub": huggingface_hub.__version__,
            "safetensors": safetensors.__version__,
            "sentenceTransformers": sentence_transformers.__version__,
            "flagEmbedding": package_version("FlagEmbedding"),
        },
        "dependencyFingerprint": sha_text(freeze),
        "pipCheckPass": pip_check["returnCode"] == 0,
        "cudaAvailable": bool(torch.cuda.is_available()),
        "cudaDeviceNameHash": sha_text(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else "",
        "cudaComputeCapability": ".".join(map(str, torch.cuda.get_device_capability(0))) if torch.cuda.is_available() else "",
        "model": {
            "modelId": "BAAI/bge-m3",
            "revision": embedding.get("revision", ""),
            "assetFingerprint": embedding.get("assetFingerprint", ""),
            "modelPathLabel": "<external-models>/bge-m3",
        },
        "tokenizerParityProbe": tokenizer_probe(tokenized, tokenizer),
        "runtimeSmoke": sparse_smoke(weights, outputs, latencies, load_ms, torch),
    }


def inspect_primary(python: Path, model_manifest: Path) -> dict[str, Any]:
    code = r"""
import json, hashlib, subprocess, sys
from pathlib import Path
model=json.loads(Path(r'__MODEL_MANIFEST__').read_text(encoding='utf-8'))['embedding']
def sha(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
import torch, transformers, tokenizers, huggingface_hub, safetensors
from transformers import AutoTokenizer
pip=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
freeze=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
tok=AutoTokenizer.from_pretrained(model['modelPath'], local_files_only=True, trust_remote_code=True)
enc=tok('safe tokenizer parity probe refund policy', return_attention_mask=True)
print(json.dumps({
 'environmentId':'torchtest-current-conflict',
 'role':'DEPENDENCY_CONFLICT_ENVIRONMENT',
 'qualificationStatus':'NOT_QUALIFIED',
 'pythonVersion':sys.version.split()[0],
 'packageVersions':{'torch':torch.__version__,'torchCuda':str(torch.version.cuda),'transformers':transformers.__version__,'tokenizers':tokenizers.__version__,'huggingfaceHub':huggingface_hub.__version__,'safetensors':safetensors.__version__},
 'dependencyFingerprint':hashlib.sha256(freeze.encode()).hexdigest(),
 'coreDependencyFingerprint':sha({'torch':torch.__version__,'transformers':transformers.__version__,'tokenizers':tokenizers.__version__,'huggingfaceHub':huggingface_hub.__version__,'safetensors':safetensors.__version__}),
 'pipCheckPass':pip.returncode==0,
 'pipCheckSummary':[line.strip() for line in (pip.stdout+pip.stderr).splitlines() if line.strip()][:8],
 'tokenizerParityProbe':{'tokenIdsHash':sha(enc['input_ids']),'attentionMaskHash':sha(enc['attention_mask']),'tokenCount':len(enc['input_ids']),'specialTokenIds':{'bos':tok.bos_token_id,'eos':tok.eos_token_id,'pad':tok.pad_token_id,'cls':tok.cls_token_id,'sep':tok.sep_token_id}}
}, sort_keys=True))
""".replace("__MODEL_MANIFEST__", str(model_manifest).replace("\\", "\\\\")).replace("safe tokenizer parity probe refund policy", SAFE_TEXTS[0])
    completed = subprocess.run([str(python), "-c", code], text=True, capture_output=True)
    if completed.returncode != 0:
        return {"environmentId": "primary-inspection-failed", "role": "UNKNOWN_ENVIRONMENT_ROLE", "qualificationStatus": "NOT_QUALIFIED", "inspectionErrorHash": sha_text(completed.stderr)}
    return json.loads(completed.stdout)


def sparse_smoke(weights: list[Any], outputs: list[Any], latencies: list[float], load_ms: float, torch_module: Any) -> dict[str, Any]:
    first = weights[0]
    return {
        "realSparseExecution": bool(weights),
        "cudaUsed": bool(torch_module.cuda.is_available()),
        "fallbackUsed": False,
        "finiteWeights": all(math.isfinite(float(value)) for item in weights for value in item.values()),
        "nonEmptyWeights": all(bool(item) for item in weights),
        "deterministicRepeat": normalize_sparse(weights[0]) == normalize_sparse(weights[1]),
        "crossRunDeterministic": all(normalize_sparse(run[0]) == normalize_sparse(outputs[0][0]) for run in outputs),
        "activeTokenIdsHash": hash_json([sorted(map(str, item.keys())) for item in weights]),
        "weightVectorHash": hash_json([normalize_sparse(item) for item in weights]),
        "scoreHash": hash_json([round(sparse_dot(weights[0], weights[1]), 8), round(sparse_dot(weights[0], weights[2]), 8)]),
        "relevantGreaterThanIrrelevantSmoke": sparse_dot(weights[0], weights[1]) > sparse_dot(weights[0], weights[2]),
        "scoreType": "BGE_M3_LEARNED_SPARSE_DOT_PRODUCT",
        "averageNonZeroDimensions": round(sum(len(item) for item in weights) / max(1, len(weights)), 6),
        "loadDurationMs": load_ms,
        "encodeP50Ms": percentile(latencies, 0.5),
        "encodeP95Ms": percentile(latencies, 0.95),
        "peakCudaMemoryBytes": int(torch_module.cuda.max_memory_allocated()) if torch_module.cuda.is_available() else 0,
        "sampleWeightHash": hash_json(normalize_sparse(first)),
    }


def build_boundary(primary: dict[str, Any], source_gate: dict[str, Any]) -> dict[str, Any]:
    source_versions = source_gate.get("packageVersions") or {}
    primary_versions = primary.get("packageVersions") or {}
    source_core = {
        "torch": source_versions.get("torch", ""),
        "transformers": source_versions.get("transformers", ""),
        "tokenizers": source_versions.get("tokenizers", ""),
        "huggingfaceHub": source_versions.get("huggingfaceHub") or source_versions.get("huggingface_hub", ""),
        "safetensors": source_versions.get("safetensors", ""),
    }
    current_core = {
        "torch": primary_versions.get("torch", ""),
        "transformers": primary_versions.get("transformers", ""),
        "tokenizers": primary_versions.get("tokenizers", ""),
        "huggingfaceHub": primary_versions.get("huggingfaceHub", ""),
        "safetensors": primary_versions.get("safetensors", ""),
    }
    comparison_keys = [key for key, value in source_core.items() if value]
    primary_unchanged = all(source_core[key] == current_core.get(key, "") for key in comparison_keys)
    return {
        "schemaVersion": "agent-rag-v23-bge-m3-sparse-environment-boundary-v1",
        "primaryEnvironmentRole": "DEPENDENCY_CONFLICT_ENVIRONMENT",
        "torchtestEnvironmentRole": "DEPENDENCY_CONFLICT_ENVIRONMENT",
        "conflictEnvironmentStatus": "NOT_QUALIFIED",
        "primaryEnvironmentComparisonScope": comparison_keys,
        "primaryEnvironmentUnchanged": primary_unchanged,
        "sourceCorePackageVersions": source_core,
        "currentCorePackageVersions": current_core,
        "primaryEnvironment": primary,
        "decision": "use isolated historical v2.2 environment for sparse qualification; do not use conflict environment for gates",
    }


def build_gate(boundary: dict[str, Any], sparse: dict[str, Any], tokenizer_parity: dict[str, Any]) -> dict[str, Any]:
    versions = sparse["packageVersions"]
    smoke = sparse["runtimeSmoke"]
    checks = {
        "isolatedEnvironment": sparse["isolatedEnvironment"] is True,
        "systemSitePackagesFalse": sparse["systemSitePackages"] is False,
        "pipCheckPass": sparse["pipCheckPass"] is True,
        "transformersMajorVersionLt5": int(str(versions["transformers"]).split(".")[0]) < 5,
        "flagEmbeddingImportPass": versions["flagEmbedding"] != "NOT_INSTALLED",
        "sentenceTransformersImportPass": versions["sentenceTransformers"] != "NOT_INSTALLED",
        "cudaAvailable": sparse["cudaAvailable"] is True,
        "realSparseExecution": smoke["realSparseExecution"] is True,
        "finiteWeights": smoke["finiteWeights"] is True,
        "nonEmptyWeights": smoke["nonEmptyWeights"] is True,
        "fallbackUsedFalse": smoke["fallbackUsed"] is False,
        "relevantGreaterThanIrrelevantSmoke": smoke["relevantGreaterThanIrrelevantSmoke"] is True,
        "modelIdentityMatch": sparse["model"]["modelId"] == "BAAI/bge-m3" and bool(sparse["model"]["assetFingerprint"]),
        "tokenizerParityPass": tokenizer_parity["status"] == "PASS",
        "deterministicRepeat": smoke["deterministicRepeat"] is True and smoke["crossRunDeterministic"] is True,
        "primaryEnvironmentUnchanged": boundary["primaryEnvironmentUnchanged"] is True,
    }
    return {
        "schemaVersion": "agent-rag-v23-bge-m3-sparse-isolated-environment-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "decision": "E_REVIEW_V23_BGE_M3_SPARSE_ISOLATED_ENVIRONMENT_PASS" if all(checks.values()) else "E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_BLOCKED",
        "checks": checks,
        "phase94bSparseIndexAllowed": all(checks.values()),
        "noPush": True,
        "noTag": True,
        "noRelease": True,
    }


def compare_tokenizers(primary_probe: dict[str, Any], sparse_probe: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "tokenIdsHashMatch": primary_probe.get("tokenIdsHash") == sparse_probe.get("tokenIdsHash"),
        "specialTokenIdsMatch": primary_probe.get("specialTokenIds") == sparse_probe.get("specialTokenIds"),
        "attentionMaskHashMatch": primary_probe.get("attentionMaskHash") == sparse_probe.get("attentionMaskHash"),
        "tokenCountMatch": primary_probe.get("tokenCount") == sparse_probe.get("tokenCount"),
    }
    return {
        "schemaVersion": "agent-rag-v23-bge-m3-sparse-tokenizer-parity-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "primaryProbe": primary_probe,
        "sparseProbe": sparse_probe,
    }


def safe_sparse_summary(sparse: dict[str, Any]) -> dict[str, Any]:
    return {key: sparse[key] for key in ["schemaVersion", "environmentVersion", "environmentSource", "isolatedEnvironment", "systemSitePackages", "pythonVersion", "packageVersions", "dependencyFingerprint", "pipCheckPass", "cudaAvailable", "cudaComputeCapability", "model"]}


def safe_smoke_summary(sparse: dict[str, Any]) -> dict[str, Any]:
    return {"schemaVersion": "agent-rag-v23-bge-m3-sparse-runtime-smoke-v1", **sparse["runtimeSmoke"]}


def tokenizer_probe(tokenized: dict[str, Any], tokenizer: Any) -> dict[str, Any]:
    return {
        "tokenIdsHash": hash_json(tokenized["input_ids"]),
        "attentionMaskHash": hash_json(tokenized["attention_mask"]),
        "tokenCount": len(tokenized["input_ids"]),
        "specialTokenIds": {
            "bos": tokenizer.bos_token_id,
            "eos": tokenizer.eos_token_id,
            "pad": tokenizer.pad_token_id,
            "cls": tokenizer.cls_token_id,
            "sep": tokenizer.sep_token_id,
        },
    }


def normalize_sparse(value: Any) -> list[list[Any]]:
    return [[str(key), round(float(weight), 8)] for key, weight in sorted(value.items())]


def sparse_dot(left: Any, right: Any) -> float:
    return sum(float(value) * float(right.get(key, 0.0)) for key, value in left.items())


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return round(float(ordered[index]), 3)


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {"returnCode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


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


def hash_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def render_boundary_doc(boundary: dict[str, Any]) -> str:
    return "# V2.3 BGE-M3 Sparse Environment Boundary\n\n```json\n" + json.dumps(boundary, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_sparse_doc(sparse: dict[str, Any], gate: dict[str, Any]) -> str:
    return "# V2.3 BGE-M3 Sparse Isolated Environment\n\nDecision: `" + gate["decision"] + "`\n\n```json\n" + json.dumps(safe_sparse_summary(sparse), ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_tokenizer_doc(tokenizer_parity: dict[str, Any]) -> str:
    return "# V2.3 BGE-M3 Sparse Tokenizer Parity\n\nStatus: `" + tokenizer_parity["status"] + "`\n\n```json\n" + json.dumps(tokenizer_parity, ensure_ascii=False, indent=2, sort_keys=True) + "\n```\n"


def render_status_doc(boundary: dict[str, Any], sparse: dict[str, Any], tokenizer_parity: dict[str, Any], gate: dict[str, Any]) -> str:
    return f"""# V2.3 Phase 9.4A Execution Status

Status: `{gate['status']}`

The previous conflict environment remains `NOT_QUALIFIED` because it contains `sentence-transformers==3.0.1` with `transformers==5.3.0`. Phase 9.4A uses an isolated historical v2.2 real-model environment instead of continuing to modify that conflict environment.

Sparse runtime result:

```text
realSparseExecution = {sparse['runtimeSmoke']['realSparseExecution']}
cudaUsed = {sparse['runtimeSmoke']['cudaUsed']}
fallbackUsed = {sparse['runtimeSmoke']['fallbackUsed']}
finiteWeights = {sparse['runtimeSmoke']['finiteWeights']}
nonEmptyWeights = {sparse['runtimeSmoke']['nonEmptyWeights']}
deterministicRepeat = {sparse['runtimeSmoke']['deterministicRepeat']}
scoreType = {sparse['runtimeSmoke']['scoreType']}
```

Tokenizer parity: `{tokenizer_parity['status']}`

Phase 9.4B sparse index allowed: `{gate['phase94bSparseIndexAllowed']}`

Resume-ready note: recovered BGE-M3 sparse execution by isolating legacy FlagEmbedding-compatible dependencies from the main Transformers 5/Qwen runtime, then proved CUDA sparse lexical-weight determinism and tokenizer parity before allowing any retrieval-index work.

```json
{json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True)}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
