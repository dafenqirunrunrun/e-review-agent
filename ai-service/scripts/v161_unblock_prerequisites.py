import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "v161_unblock_prerequisites.json"
REPORT = ROOT / "docs" / "125_v161_unblock_prerequisites.md"
DEFAULT_REAL_JSON = r"D:\EReviewAgent\data-private\banglishrev\reviews v1.json"
DEFAULT_VLM_CANDIDATES = [
    r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct",
    r"D:\EReviewAgent\models\Qwen2.5-VL-3B-Instruct",
]
DEFAULT_TEXT_MODEL_DIRS = [
    r"D:\EReviewAgent\models\bge-m3",
    r"D:\EReviewAgent\models\rag-reranker",
    r"D:\EReviewAgent\models\Qwen3-1.7B",
]
DEFAULT_TORCH_PYTHON = r"D:\anaconda\envs\torchtest\python.exe"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def exists(path: str) -> bool:
    return Path(path).exists()


def vlm_model_ready(path: str) -> bool:
    root = Path(path)
    if not root.is_dir() or not (root / "config.json").exists():
        return False
    files = [item for item in root.rglob("*") if item.is_file()]
    names = {item.name for item in files}
    has_processor = any(
        name in names
        for name in [
            "preprocessor_config.json",
            "processor_config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
        ]
    )
    has_weights = any(item.suffix == ".safetensors" or item.name.startswith("pytorch_model") for item in files)
    return has_processor and has_weights


def split_paths(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(os.pathsep) if item.strip()]


def git_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def git_tracked_matches(patterns: list[str]) -> list[str]:
    matches = []
    for file_name in git_files():
        lowered = file_name.lower()
        if any(lowered.startswith(pattern.lower()) for pattern in patterns):
            matches.append(file_name)
    return matches


def git_tracked_suffix_matches(suffixes: list[str]) -> list[str]:
    matches = []
    for file_name in git_files():
        lowered = file_name.lower()
        if any(lowered.endswith(suffix.lower()) for suffix in suffixes):
            matches.append(file_name)
    return matches


def torch_probe(python_executable: str) -> dict:
    code = (
        "import json\n"
        "try:\n"
        " import torch\n"
        " print(json.dumps({'torch_available': True, 'cuda_available': torch.cuda.is_available(), "
        "'device_count': torch.cuda.device_count()}))\n"
        "except Exception as exc:\n"
        " print(json.dumps({'torch_available': False, 'error': str(exc)}))\n"
    )
    completed = subprocess.run(
        [python_executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        payload = json.loads((completed.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        payload = {"torch_available": False, "error": (completed.stderr or completed.stdout or "").strip()}
    payload["python"] = python_executable
    payload["return_code"] = completed.returncode
    return payload


def display_path(path: str, fallback: str) -> str:
    normalized = path.replace("\\", "/")
    lowered = normalized.lower()
    if "/data-private/" in lowered:
        return "<repo-external>/data-private/" + normalized.split("/data-private/", 1)[1]
    if "/models/" in lowered:
        return "<repo-external>/models/" + normalized.split("/models/", 1)[1]
    if "/envs/" in lowered:
        return "<local-conda>/envs/" + normalized.split("/envs/", 1)[1]
    return fallback


def public_text(value: str) -> str:
    replacements = {
        DEFAULT_REAL_JSON: display_path(DEFAULT_REAL_JSON, "<repo-external>/data-private/banglishrev/reviews v1.json"),
        DEFAULT_TORCH_PYTHON: display_path(DEFAULT_TORCH_PYTHON, "<local-conda>/envs/torchtest/python.exe"),
        DEFAULT_TORCH_PYTHON.replace("\\", "\\\\"): display_path(DEFAULT_TORCH_PYTHON, "<local-conda>/envs/torchtest/python.exe"),
    }
    for path in DEFAULT_VLM_CANDIDATES + DEFAULT_TEXT_MODEL_DIRS:
        replacements[path] = display_path(path, "<repo-external>")
    public = value
    for private, replacement in replacements.items():
        public = public.replace(private, replacement)
    return public


def markdown(result: dict) -> str:
    rows = "\n".join(
        f"| {item['name']} | `{item['status']}` | {public_text(item['evidence'])} | {item['action']} |"
        for item in result["checks"]
    )
    blockers = "\n".join(f"- {item}" for item in result["blockers"]) or "- none"
    return f"""# v1.6.1 Unblock Prerequisites Check

## Conclusion

`{result['marker']}`

This report only checks whether the local environment has the prerequisites needed to continue real external text evaluation, real multimodal evaluation, VLM inference, and SFT readiness auditing. It must not be interpreted as a real evaluation PASS.

## Checks

| Check | Status | Evidence | Required action |
| --- | --- | --- | --- |
{rows}

## Blockers

{blockers}

## Next Steps

1. Place the compliant real review JSON outside Git, for example `<repo-external>/data-private/banglishrev/reviews v1.json`.
2. Place local VLM weights outside Git, for example `<repo-external>/models/Qwen3-VL-2B-Instruct`, or configure an equivalent repo-external model path.
3. If your local paths differ from the defaults, pass `-RealJson`, `-VlmCandidates`, `-TextModelDirs`, and `-TorchPython` to `scripts/e-review-v161-unblock-prerequisites.ps1`, or set `V161_REAL_TEXT_SOURCE`, `V161_VLM_MODEL_DIRS`, `V161_TEXT_MODEL_DIRS`, and `V161_TORCH_PYTHON`.
4. Rerun `scripts/e-review-realworld-ingest.ps1`, `scripts/e-review-vlm-visual-eval.ps1`, `scripts/e-review-multimodal-ablation-eval.ps1`, `scripts/e-review-multimodal-route-calibration.ps1`, and `scripts/e-review-v161-final-gate.ps1`.
5. Consider a release tag only after the final gate reports `V161_FINAL_GATE_PASS`.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--real-json",
        default=os.environ.get("V161_REAL_TEXT_SOURCE", DEFAULT_REAL_JSON),
        help="Repo-external compliant real review JSON path.",
    )
    parser.add_argument(
        "--vlm-candidates",
        default=os.environ.get("V161_VLM_MODEL_DIRS"),
        help=f"Repo-external VLM model directories separated by os.pathsep ({os.pathsep!r}).",
    )
    parser.add_argument(
        "--text-model-dirs",
        default=os.environ.get("V161_TEXT_MODEL_DIRS"),
        help=f"Repo-external text model directories separated by os.pathsep ({os.pathsep!r}).",
    )
    parser.add_argument(
        "--torch-python",
        default=os.environ.get("V161_TORCH_PYTHON", DEFAULT_TORCH_PYTHON),
        help="Python executable used for torch/cuda probing.",
    )
    return parser.parse_args()


def build_result(real_json: str, vlm_candidates: list[str], model_dirs: list[str], torchtest: str) -> dict:
    default_torch = torch_probe(sys.executable)
    torchtest_probe = torch_probe(torchtest) if exists(torchtest) else {
        "torch_available": False,
        "python": torchtest,
        "error": "python not found",
    }
    private_matches = git_tracked_matches(["data-private/", "data/real_world/raw_private/", ".cache/huggingface/", "models/"])
    weight_matches = git_tracked_suffix_matches([".safetensors", ".bin", ".gguf", ".ckpt", ".faiss", ".onnx", ".pt", ".pth"])

    real_json_exists = exists(real_json)
    vlm_ready = any(vlm_model_ready(path) for path in vlm_candidates)
    checks = [
        {
            "name": "real_text_source_file",
            "status": "READY" if real_json_exists else "BLOCKED",
            "evidence": real_json,
            "action": "Run realworld ingest." if real_json_exists else "Provide official BanglishRev JSON outside Git.",
        },
        {
            "name": "local_vlm_model",
            "status": "READY" if vlm_ready else "BLOCKED",
            "evidence": ", ".join(vlm_candidates),
            "action": "Run VLM smoke/eval." if vlm_ready else "Place complete Qwen3-VL/Qwen2.5-VL config, processor/tokenizer, and weights outside Git.",
        },
        {
            "name": "existing_text_models",
            "status": "READY" if all(exists(path) for path in model_dirs) else "BLOCKED",
            "evidence": ", ".join(model_dirs),
            "action": "Keep model weights outside Git.",
        },
        {
            "name": "torch_cuda_environment",
            "status": "READY" if torchtest_probe.get("torch_available") and torchtest_probe.get("cuda_available") else "CHECK",
            "evidence": json.dumps(torchtest_probe, ensure_ascii=False),
            "action": "Use torchtest Python for BGE/reranker/VLM checks.",
        },
        {
            "name": "private_data_not_tracked",
            "status": "READY" if not private_matches else "BLOCKED",
            "evidence": f"tracked_matches={len(private_matches)}",
            "action": "Remove private data/model paths from Git if any are tracked.",
        },
        {
            "name": "model_weights_not_tracked",
            "status": "READY" if not weight_matches else "BLOCKED",
            "evidence": f"tracked_matches={len(weight_matches)}",
            "action": "Remove model weights/index binaries from Git if any are tracked.",
        },
    ]
    blockers = [f"{item['name']}: {item['action']}" for item in checks if item["status"] == "BLOCKED"]
    result = {
        "marker": "V161_UNBLOCK_PREREQUISITES_READY" if not blockers else "V161_UNBLOCK_PREREQUISITES_BLOCKED",
        "inputs": {
            "real_json": real_json,
            "vlm_candidates": vlm_candidates,
            "text_model_dirs": model_dirs,
            "torch_python": torchtest,
        },
        "checks": checks,
        "blockers": blockers,
        "torch_default": default_torch,
        "torch_torchtest": torchtest_probe,
    }
    return result


def main() -> int:
    args = parse_args()
    real_json = args.real_json
    vlm_candidates = split_paths(args.vlm_candidates, DEFAULT_VLM_CANDIDATES)
    model_dirs = split_paths(args.text_model_dirs, DEFAULT_TEXT_MODEL_DIRS)
    result = build_result(real_json, vlm_candidates, model_dirs, args.torch_python)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(markdown(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
