from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "real-model-chain" / "python-environment-gate.json"


def main() -> int:
    checks: dict[str, object] = {
        "pythonExecutableLabel": Path(sys.executable).name,
        "pythonStarts": True,
    }
    failures: list[str] = []

    pip_check = subprocess.run([sys.executable, "-m", "pip", "check"], text=True, capture_output=True, timeout=120)
    checks["pipCheckPass"] = pip_check.returncode == 0
    checks["pipCheckOutput"] = (pip_check.stdout + pip_check.stderr).strip()[:1000]
    if pip_check.returncode != 0:
        failures.append("PIP_CHECK_FAILED")

    try:
        import torch

        checks["torchVersion"] = torch.__version__
        checks["cudaVersion"] = torch.version.cuda
        checks["torchCudaPass"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            checks["gpuName"] = props.name
            checks["totalMemoryBytes"] = props.total_memory
            checks["computeCapability"] = [props.major, props.minor]
        else:
            failures.append("TORCH_CUDA_UNAVAILABLE")
    except Exception as exc:
        checks["torchError"] = type(exc).__name__
        failures.append("TORCH_IMPORT_FAILED")

    for module_name, failure in [
        ("faiss", "FAISS_IMPORT_FAILED"),
        ("FlagEmbedding", "FLAGEMBEDDING_IMPORT_FAILED"),
        ("transformers", "TRANSFORMERS_IMPORT_FAILED"),
        ("accelerate", "ACCELERATE_IMPORT_FAILED"),
    ]:
        try:
            module = __import__(module_name)
            checks[module_name] = getattr(module, "__version__", "unknown")
        except Exception as exc:
            checks[module_name] = f"IMPORT_FAILED:{type(exc).__name__}"
            failures.append(failure)

    transformers_version = str(checks.get("transformers") or "")
    if transformers_version and not transformers_version.startswith("IMPORT_FAILED"):
        if _version_tuple(transformers_version) < (4, 51, 0):
            failures.append("TRANSFORMERS_VERSION_BELOW_QWEN3_MINIMUM")

    checks["flagRerankerImportPass"] = False
    if importlib.util.find_spec("FlagEmbedding"):
        try:
            from FlagEmbedding import FlagReranker  # noqa: F401

            checks["flagRerankerImportPass"] = True
        except Exception as exc:
            checks["flagRerankerImportError"] = type(exc).__name__
            failures.append("FLAGRERANKER_IMPORT_FAILED")

    checks["qwen3ArchitectureRecognized"] = False
    try:
        from transformers import AutoConfig

        model_source = os.getenv("E_REVIEW_LOCAL_QWEN_MODEL_DIR", "").strip() or "Qwen/Qwen3-1.7B"
        config = AutoConfig.from_pretrained(model_source, trust_remote_code=False, local_files_only=True)
        checks["qwen3ArchitectureRecognized"] = bool(getattr(config, "model_type", "") == "qwen3")
    except Exception as exc:
        checks["qwen3ArchitectureError"] = type(exc).__name__
        failures.append("QWEN3_ARCHITECTURE_NOT_RECOGNIZED")

    status = "PASS" if not failures else "BLOCKED"
    payload = {
        "status": status,
        "tokens": ["E_REVIEW_V22_PYTHON_ENVIRONMENT_PASS"] if status == "PASS" else ["E_REVIEW_V22_PYTHON_ENVIRONMENT_BLOCKED"],
        "failures": sorted(set(failures)),
        "checks": checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if status == "PASS":
        print("E_REVIEW_V22_PYTHON_ENVIRONMENT_PASS")
        return 0
    print("E_REVIEW_V22_PYTHON_ENVIRONMENT_BLOCKED")
    for failure in payload["failures"]:
        print(failure)
    return 2


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = []
    for raw in value.split(".")[:3]:
        digits = "".join(ch for ch in raw if ch.isdigit())
        parts.append(int(digits or "0"))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)  # type: ignore[return-value]


if __name__ == "__main__":
    raise SystemExit(main())
