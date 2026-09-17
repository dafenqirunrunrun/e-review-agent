import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_MANIFEST = ROOT / "data" / "real_world" / "multimodal_manifest" / "real_multimodal_external_test.jsonl"
OUT = ROOT / "data" / "multimodal" / "eval" / "multimodal_ablation_results.json"
FAILURES = ROOT / "data" / "multimodal" / "eval" / "multimodal_failures.jsonl"
REPORT = ROOT / "docs" / "113_v161_multimodal_ablation_eval_report.md"
REQUIRED_EXTERNAL_MULTIMODAL_COUNT = 40


MODES = [
    "text_only",
    "image_only",
    "text_image",
    "text_image_hybrid_rag",
]

METRIC_KEYS = [
    "schema_valid_rate",
    "risk_type_accuracy",
    "risk_type_macro_f1",
    "risk_level_accuracy",
    "risk_level_macro_f1",
    "evidence_support_rate",
    "visual_evidence_support_rate",
    "unsupported_claim_rate",
    "visual_unsupported_claim_rate",
    "text_image_consistency_macro_f1",
    "need_human_review_accuracy",
    "human_review_precision",
    "human_review_recall",
    "human_review_f1",
    "high_risk_review_recall",
    "unsafe_auto_pass_rate",
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


def empty_mode_metrics() -> dict:
    return {mode: {key: None for key in METRIC_KEYS} for mode in MODES}


def build_result() -> dict:
    external_count = count_jsonl(EXTERNAL_MANIFEST)
    model_available = vlm_model_ready(configured_model_dir())
    blocking_reasons = []
    if external_count < REQUIRED_EXTERNAL_MULTIMODAL_COUNT:
        blocking_reasons.append(
            f"real multimodal external test set requires at least {REQUIRED_EXTERNAL_MULTIMODAL_COUNT} samples; current={external_count}"
        )
    if not model_available:
        blocking_reasons.append("local VLM config, processor/tokenizer, and weights are not available outside Git")

    return {
        "marker": "MULTIMODAL_ABLATION_EVAL_BLOCKED" if blocking_reasons else "MULTIMODAL_ABLATION_EVAL_READY_FOR_MODEL_RUN",
        "external_multimodal_count": external_count,
        "required_external_multimodal_count": REQUIRED_EXTERNAL_MULTIMODAL_COUNT,
        "model_available": model_available,
        "evaluated_modes": MODES,
        "metrics": empty_mode_metrics(),
        "blocking_reasons": blocking_reasons,
        "notes": [
            "All four modes must be reported together once real external multimodal data and VLM inference are available.",
            "Null metric values mean the ablation was not executed; they are not zero scores.",
            "External multimodal test samples must not be used for prompt selection, training, or threshold calibration.",
        ],
    }


def report_text(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["blocking_reasons"]) or "- none"
    mode_rows = "\n".join(f"| `{mode}` | not executed |" for mode in result["evaluated_modes"])
    metric_lines = "\n".join(f"- `{key}`" for key in METRIC_KEYS)
    return f"""# v1.6.1 Multimodal Ablation Evaluation Report

## Conclusion

`{result['marker']}`

- External multimodal count: `{result['external_multimodal_count']}`
- Required external multimodal count: `{result['required_external_multimodal_count']}`
- Model available: `{result['model_available']}`

## Four Required Modes

| Mode | Status |
| --- | --- |
{mode_rows}

## Required Metrics

{metric_lines}

## Blocking Reasons

{blockers}

## Evidence Boundary

The four-group comparison is intentionally blocked until the same isolated real
multimodal external test set can be evaluated across Text Only, Image Only,
Text+Image, and Text+Image+Hybrid RAG. No synthetic or manually inferred visual
signals are used as a substitute for real VLM output.
"""


def main() -> int:
    result = build_result()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    FAILURES.write_text("", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
