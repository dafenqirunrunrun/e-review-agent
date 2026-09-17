import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "data" / "real_world" / "external_test" / "real_reviews_external_test_200.jsonl"
OUT = ROOT / "data" / "rag" / "audit" / "qwen_realworld_external_eval_results.json"
REPORT = ROOT / "docs" / "114_v161_qwen_realworld_external_eval_report.md"
REQUIRED_EXTERNAL_COUNT = 200


EVAL_MODES = [
    "qwen3_prompt_only",
    "qwen3_synthetic_rag",
    "qwen3_real_rag",
    "qwen3_synthetic_plus_real_hybrid_rag",
]

METRIC_KEYS = [
    "risk_type_accuracy",
    "risk_type_macro_f1",
    "risk_level_accuracy",
    "risk_level_macro_f1",
    "schema_valid_rate",
    "evidence_support_rate",
    "unsupported_claim_rate",
    "human_review_precision",
    "human_review_recall",
    "high_risk_review_recall",
    "unsafe_auto_pass_rate",
    "fallback_rate",
    "avg_latency_ms",
]


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def empty_mode_results() -> dict:
    return {
        mode: {key: None for key in METRIC_KEYS}
        for mode in EVAL_MODES
    }


def build_result() -> dict:
    count = count_jsonl(EXTERNAL)
    blocked = count < REQUIRED_EXTERNAL_COUNT
    blockers = []
    if blocked:
        blockers.append(
            f"real external text test set requires at least {REQUIRED_EXTERNAL_COUNT} samples; current={count}"
        )

    return {
        "marker": "REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED" if blocked else "REALWORLD_QWEN_EXTERNAL_EVAL_READY_FOR_MODEL_RUN",
        "real_external_count": count,
        "required_real_external_count": REQUIRED_EXTERNAL_COUNT,
        "input_dataset": "data/real_world/external_test/real_reviews_external_test_200.jsonl",
        "evaluated_modes": EVAL_MODES,
        "metrics": empty_mode_results(),
        "blocking_reasons": blockers,
        "notes": [
            "No real-world Qwen downstream metric is reported unless the isolated external test set is available.",
            "The external test set must not be used for indexing, prompt selection, fusion-weight tuning, or threshold calibration.",
            "Null metric values mean the model comparison was not executed; they are not zero scores.",
        ],
    }


def report_text(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["blocking_reasons"]) or "- none"
    mode_lines = "\n".join(f"- `{mode}`: not executed" for mode in result["evaluated_modes"])
    metric_lines = "\n".join(f"- `{key}`" for key in METRIC_KEYS)
    return f"""# v1.6.1 Qwen Real-World External Evaluation Report

## Conclusion

`{result['marker']}`

- Real external text count: `{result['real_external_count']}`
- Required real external text count: `{result['required_real_external_count']}`
- Input dataset: `{result['input_dataset']}`

## Compared Modes

{mode_lines}

## Required Metrics

{metric_lines}

## Blocking Reasons

{blockers}

## Evidence Boundary

This report intentionally does not provide Prompt-only, Synthetic RAG, Real RAG,
or Synthetic+Real Hybrid RAG metrics while the isolated real-world external test
set is unavailable. Synthetic data must not be renamed or reused as real external
evidence.
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
