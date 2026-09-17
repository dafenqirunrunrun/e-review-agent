import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_MANIFEST = ROOT / "data" / "real_world" / "multimodal_manifest" / "real_multimodal_external_test.jsonl"
OUT = ROOT / "data" / "multimodal" / "eval" / "vlm_visual_eval_results.json"
REPORT = ROOT / "docs" / "128_v161_vlm_visual_evidence_eval_report.md"
REQUIRED_EXTERNAL_MULTIMODAL_COUNT = 40


METRIC_KEYS = [
    "visual_schema_valid_rate",
    "visual_field_complete_rate",
    "image_quality_accuracy",
    "ocr_exact_match",
    "ocr_character_f1",
    "package_damage_f1",
    "product_damage_f1",
    "leakage_f1",
    "missing_part_f1",
    "product_mismatch_f1",
    "irrelevant_image_f1",
    "text_image_consistency_macro_f1",
    "visual_evidence_support_rate",
    "visual_unsupported_claim_rate",
    "privacy_risk_recall",
    "fallback_rate",
    "avg_latency_ms",
    "p95_latency_ms",
    "gpu_peak_memory_mb",
]


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def configured_model_dir() -> Path:
    return Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", "D:/EReviewAgent/models/Qwen3-VL-2B-Instruct"))


def vlm_model_ready(model_dir: Path) -> bool:
    if not model_dir.is_dir() or not (model_dir / "config.json").exists():
        return False
    files = [item for item in model_dir.rglob("*") if item.is_file()]
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


def empty_metrics() -> dict:
    return {key: None for key in METRIC_KEYS}


def build_result() -> dict:
    external_count = count_jsonl(EXTERNAL_MANIFEST)
    model_available = vlm_model_ready(configured_model_dir())
    blocking_reasons = []
    if external_count < REQUIRED_EXTERNAL_MULTIMODAL_COUNT:
        blocking_reasons.append(
            f"real multimodal external test set requires at least {REQUIRED_EXTERNAL_MULTIMODAL_COUNT} samples; current={external_count}"
        )
    if not model_available:
        blocking_reasons.append("local Qwen3-VL/Qwen2.5-VL config, processor/tokenizer, and weights are not available outside Git")

    return {
        "marker": "MULTIMODAL_VLM_EVAL_BLOCKED" if blocking_reasons else "MULTIMODAL_VLM_EVAL_READY_FOR_REAL_IMAGE_RUN",
        "external_multimodal_count": external_count,
        "required_external_multimodal_count": REQUIRED_EXTERNAL_MULTIMODAL_COUNT,
        "model_available": model_available,
        "model_dir_kind": "repo_external_configured_path",
        "metrics": empty_metrics(),
        "blocking_reasons": blocking_reasons,
        "notes": [
            "Metric values remain null until real image inference is executed on an isolated external multimodal test set.",
            "The script does not use image filenames, paths, or manual labels as visual understanding.",
            "Original real images must remain outside Git.",
        ],
    }


def report_text(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["blocking_reasons"]) or "- none"
    metrics = "\n".join(f"- `{key}`: not executed" for key in METRIC_KEYS)
    return f"""# v1.6.1 VLM Visual Evidence Evaluation Report

## Conclusion

`{result['marker']}`

- External multimodal count: `{result['external_multimodal_count']}`
- Required external multimodal count: `{result['required_external_multimodal_count']}`
- Model available: `{result['model_available']}`
- Model directory kind: `{result['model_dir_kind']}`

## Required Metrics

{metrics}

## Blocking Reasons

{blockers}

## Evidence Boundary

This report evaluates the independent VLM visual-evidence extraction path. It
does not report visual evidence support, unsupported visual claim rate, OCR, or
image-quality metrics while real external multimodal samples and local VLM
weights are unavailable.
"""


def main() -> int:
    result = build_result()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
