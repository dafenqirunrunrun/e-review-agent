import json
import os
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "vlm-smoke"
OUT = RUNTIME / "qwen3_vl_download_result.json"
REPO_ID = "Qwen/Qwen3-VL-2B-Instruct"


def in_git_tree(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def summarize_dir(path: Path) -> dict:
    if not path.exists():
        return {
            "exists": False,
            "file_count": 0,
            "total_size_mb": 0,
            "has_config": False,
            "has_processor_or_tokenizer": False,
            "has_weight_file": False,
            "has_weight_index": False,
            "has_generation_config": False,
        }
    files = [item for item in path.rglob("*") if item.is_file()]
    names = {item.name for item in files}
    return {
        "exists": True,
        "file_count": len(files),
        "total_size_mb": round(sum(item.stat().st_size for item in files) / 1024 / 1024, 2),
        "has_config": "config.json" in names,
        "has_processor_or_tokenizer": any(
            name in names
            for name in [
                "preprocessor_config.json",
                "processor_config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.json",
                "merges.txt",
            ]
        ),
        "has_weight_file": any(item.suffix == ".safetensors" or item.name.startswith("pytorch_model") for item in files),
        "has_weight_index": any(item.name.endswith(".index.json") for item in files),
        "has_generation_config": "generation_config.json" in names,
    }


def result_payload(marker: str, **extra) -> dict:
    model_dir = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct"))
    payload = {
        "marker": marker,
        "repo_id": REPO_ID,
        "model_dir": str(model_dir),
        "model_dir_in_git_tree": in_git_tree(model_dir),
        "hf_home": os.getenv("HF_HOME"),
        "huggingface_hub_cache": os.getenv("HUGGINGFACE_HUB_CACHE"),
        "directory_summary": summarize_dir(model_dir),
    }
    payload.update(extra)
    return payload


def write_result(payload: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def validate_ready(model_dir: Path) -> tuple[bool, list[str]]:
    blockers = []
    summary = summarize_dir(model_dir)
    if in_git_tree(model_dir):
        blockers.append("MODEL_DIR_INSIDE_GIT_TREE")
    if summary["file_count"] <= 5:
        blockers.append("MODEL_FILE_COUNT_TOO_SMALL")
    if not summary["has_config"]:
        blockers.append("CONFIG_JSON_MISSING")
    if not summary["has_processor_or_tokenizer"]:
        blockers.append("PROCESSOR_OR_TOKENIZER_MISSING")
    if not summary["has_weight_file"]:
        blockers.append("WEIGHT_FILE_MISSING")
    return not blockers, blockers


def main() -> int:
    model_dir = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", r"D:\EReviewAgent\models\Qwen3-VL-2B-Instruct"))
    if in_git_tree(model_dir):
        payload = result_payload("VLM_MODEL_DOWNLOAD_BLOCKED_MODEL_DIR_INSIDE_GIT", error_type="safety")
        write_result(payload)
        print(json.dumps(payload, ensure_ascii=False))
        print(payload["marker"])
        return 2

    try:
        from huggingface_hub import model_info, snapshot_download

        info = model_info(REPO_ID)
        model_dir.mkdir(parents=True, exist_ok=True)
        local_path = snapshot_download(
            repo_id=REPO_ID,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        ready, blockers = validate_ready(model_dir)
        marker = "VLM_MODEL_READY" if ready else "VLM_MODEL_DOWNLOAD_INCOMPLETE"
        payload = result_payload(
            marker,
            model_info={
                "id": getattr(info, "id", REPO_ID),
                "sha": getattr(info, "sha", None),
                "private": getattr(info, "private", None),
                "gated": getattr(info, "gated", None),
                "author": getattr(info, "author", None),
                "license": getattr(getattr(info, "cardData", None), "license", None)
                if not isinstance(getattr(info, "cardData", None), dict)
                else getattr(info, "cardData", {}).get("license"),
            },
            local_path=local_path,
            blockers=blockers,
        )
        write_result(payload)
        print(json.dumps(payload, ensure_ascii=False))
        print(marker)
        return 0 if ready else 3
    except Exception as exc:
        message = str(exc)
        error_type = type(exc).__name__
        marker = "VLM_MODEL_DOWNLOAD_BLOCKED_NETWORK" if "SSL" in message or "TLS" in message or "Connect" in error_type else "VLM_MODEL_DOWNLOAD_BLOCKED"
        payload = result_payload(
            marker,
            error_type=error_type,
            error_message=message,
            traceback_tail=traceback.format_exc().splitlines()[-8:],
            retry_suggestion="Retry with a working HTTPS route to official Hugging Face or use an official ModelScope source; do not use third-party repacks.",
        )
        write_result(payload)
        print(json.dumps(payload, ensure_ascii=False))
        print(marker)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
