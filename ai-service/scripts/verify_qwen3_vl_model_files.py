import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "vlm-smoke"
OUT = RUNTIME / "qwen3_vl_model_verify_result.json"
REPO_ID = "Qwen/Qwen3-VL-2B-Instruct"
REQUIRED_FILES = [
    "chat_template.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "video_preprocessor_config.json",
    "vocab.json",
]


def in_git_tree(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def read_json(path: Path) -> tuple[bool, str | None]:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def summarize(model_dir: Path) -> dict:
    files = [item for item in model_dir.rglob("*") if item.is_file()] if model_dir.exists() else []
    names = {item.name for item in files}
    partial_files = [str(item.relative_to(model_dir)) for item in files if item.name.endswith(".part")]
    safetensors = [item for item in files if item.suffix == ".safetensors"]
    model_weight = model_dir / "model.safetensors"
    required = {}
    for name in REQUIRED_FILES:
        path = model_dir / name
        required[name] = {
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
            "non_empty": path.exists() and path.stat().st_size > 0,
        }
    return {
        "exists": model_dir.exists(),
        "file_count": len(files),
        "total_size_mb": round(sum(item.stat().st_size for item in files) / 1024 / 1024, 2),
        "required_files": required,
        "missing_required_files": [name for name, info in required.items() if not info["exists"]],
        "empty_required_files": [name for name, info in required.items() if info["exists"] and not info["non_empty"]],
        "partial_files": partial_files,
        "has_config": "config.json" in names,
        "has_tokenizer_json": "tokenizer.json" in names,
        "has_processor": "preprocessor_config.json" in names,
        "safetensors_files": [str(item.relative_to(model_dir)) for item in safetensors],
        "has_safetensors": bool(safetensors),
        "model_safetensors_size_mb": round(model_weight.stat().st_size / 1024 / 1024, 2) if model_weight.exists() else 0,
        "model_safetensors_reasonable_size": model_weight.exists() and model_weight.stat().st_size > 1024 * 1024 * 1024,
        "weight_index_files": [str(item.relative_to(model_dir)) for item in files if item.name.endswith(".index.json")],
        "has_generation_config": "generation_config.json" in names,
    }


def write(payload: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    model_dir = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct"))
    summary = summarize(model_dir)
    checks = {
        "model_dir_outside_git": not in_git_tree(model_dir),
        "required_files_exist": not summary["missing_required_files"],
        "required_files_non_empty": not summary["empty_required_files"],
        "no_part_files": not summary["partial_files"],
        "model_safetensors_reasonable_size": summary["model_safetensors_reasonable_size"],
        "config_json_parseable": False,
        "tokenizer_json_parseable": False,
        "tokenizer_config_json_parseable": False,
        "auto_config": False,
        "auto_processor": False,
        "safetensors_header_readable": False,
        "qwen3_vl_model_class": False,
    }
    details = {}
    errors = []

    for key, filename in [
        ("config_json_parseable", "config.json"),
        ("tokenizer_json_parseable", "tokenizer.json"),
        ("tokenizer_config_json_parseable", "tokenizer_config.json"),
    ]:
        path = model_dir / filename
        if path.exists():
            ok, error = read_json(path)
            checks[key] = ok
            if error:
                errors.append({"check": key, "error": error})

    try:
        from transformers import AutoConfig, AutoProcessor, Qwen3VLForConditionalGeneration

        details["transformers_qwen3_vl_import"] = True
        if checks["config_json_parseable"]:
            config = AutoConfig.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
            checks["auto_config"] = True
            details["auto_config_model_type"] = getattr(config, "model_type", None)
            details["auto_config_architectures"] = getattr(config, "architectures", None)
        if summary["has_processor"] and summary["has_tokenizer_json"]:
            AutoProcessor.from_pretrained(str(model_dir), local_files_only=True, trust_remote_code=False)
            checks["auto_processor"] = True
        checks["qwen3_vl_model_class"] = Qwen3VLForConditionalGeneration is not None
    except Exception as exc:
        details["transformers_qwen3_vl_import"] = False
        errors.append({"check": "transformers_auto_load", "error_type": type(exc).__name__, "error_message": str(exc)})

    weight_path = model_dir / "model.safetensors"
    if weight_path.exists() and weight_path.stat().st_size > 0:
        try:
            from safetensors import safe_open

            with safe_open(str(weight_path), framework="pt", device="cpu") as handle:
                keys = list(handle.keys())
                checks["safetensors_header_readable"] = bool(keys)
                details["safetensors_key_count"] = len(keys)
                details["safetensors_key_sample"] = keys[:10]
        except Exception as exc:
            errors.append({"check": "safetensors_header_readable", "error_type": type(exc).__name__, "error_message": str(exc)})

    blockers = [name for name, passed in checks.items() if not passed]
    marker = "VLM_MODEL_READY" if not blockers else "VLM_MODEL_NOT_READY"
    payload = {
        "marker": marker,
        "repo_id": REPO_ID,
        "model_dir": str(model_dir),
        "summary": summary,
        "checks": checks,
        "details": details,
        "blockers": blockers,
        "errors": errors,
    }
    write(payload)
    print(json.dumps(payload, ensure_ascii=False))
    print(marker)
    return 0 if marker == "VLM_MODEL_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
