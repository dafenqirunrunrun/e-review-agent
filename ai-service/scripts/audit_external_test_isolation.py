import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "external_test_isolation_audit.json"
REPORT = ROOT / "docs" / "130_v161_external_test_isolation_audit.md"

EXTERNAL_TEST_TOKENS = [
    "real_reviews_external_test_200.jsonl",
    "real_multimodal_external_test.jsonl",
    "data/real_world/external_test",
    "data\\real_world\\external_test",
    "real_world/external_test",
    "real_world\\external_test",
    "multimodal_manifest/real_multimodal_external_test",
    "multimodal_manifest\\real_multimodal_external_test",
]

ALLOWED_CODE_PATHS = {
    "ai-service/scripts/audit_external_test_isolation.py",
    "ai-service/scripts/audit_sft_data_readiness.py",
    "ai-service/scripts/audit_realworld_sft_readiness.py",
    "ai-service/scripts/build_realworld_split.py",
    "ai-service/scripts/build_realworld_text_split.py",
    "ai-service/scripts/calibrate_realworld_multimodal_route.py",
    "ai-service/scripts/eval_realworld_multimodal_ablation.py",
    "ai-service/scripts/eval_realworld_qwen_text_external.py",
    "ai-service/scripts/eval_realworld_text_rag_external.py",
    "ai-service/scripts/eval_realworld_vlm_external.py",
    "ai-service/scripts/eval_multimodal_ablation.py",
    "ai-service/scripts/eval_qwen_realworld_external.py",
    "ai-service/scripts/eval_rag_validity_and_external.py",
    "ai-service/scripts/eval_vlm_visual_evidence.py",
    "ai-service/scripts/v161_final_gate.py",
    "ai-service/scripts/v161_final_status_summary.py",
    "ai-service/scripts/v161_requirement_traceability.py",
    "scripts/e-review-multimodal-ablation-eval.ps1",
    "scripts/e-review-qwen-realworld-external-eval.ps1",
    "scripts/e-review-rag-validity-external-eval.ps1",
    "scripts/e-review-vlm-visual-eval.ps1",
    "scripts/e-review-realworld-vlm-eval.ps1",
}

SENSITIVE_PURPOSE_HINTS = [
    "build_rag_index",
    "train",
    "sft",
    "dpo",
    "qlora",
    "prompt",
    "threshold",
    "calibrat",
    "fusion",
    "reranker",
]

SCAN_DIRS = [
    "ai-service/app",
    "ai-service/scripts",
    "scripts",
]

SCAN_SUFFIXES = {".py", ".ps1", ".java", ".js", ".vue", ".ts"}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def iter_code_files():
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in SCAN_SUFFIXES:
                yield path


def token_hits(text: str) -> list[str]:
    normalized = text.replace("\\", "/")
    hits = []
    for token in EXTERNAL_TEST_TOKENS:
        if token in text or token.replace("\\", "/") in normalized:
            hits.append(token)
    return sorted(set(hits))


def audit_code_references() -> tuple[list[dict], list[dict]]:
    allowed_references = []
    violations = []
    for path in iter_code_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = token_hits(text)
        if not hits:
            continue
        relative = rel(path)
        row = {
            "path": relative,
            "tokens": hits,
            "purpose_hint": next((hint for hint in SENSITIVE_PURPOSE_HINTS if hint in relative.lower()), "none"),
        }
        if relative in ALLOWED_CODE_PATHS:
            allowed_references.append(row)
        else:
            violations.append(row)
    return allowed_references, violations


def audit_index_metadata() -> list[dict]:
    violations = []
    for path in (ROOT / "data" / "rag" / "index").glob("*meta*.json"):
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = token_hits(text)
        if hits:
            violations.append({"path": rel(path), "tokens": hits})
    return violations


def markdown(result: dict) -> str:
    allowed_rows = "\n".join(
        f"| `{row['path']}` | {', '.join(f'`{token}`' for token in row['tokens'])} |"
        for row in result["allowed_references"]
    ) or "| - | - |"
    violation_rows = "\n".join(
        f"| `{row['path']}` | {', '.join(f'`{token}`' for token in row['tokens'])} | {row.get('purpose_hint', 'none')} |"
        for row in result["violations"]
    ) or "| - | - | - |"
    index_rows = "\n".join(
        f"| `{row['path']}` | {', '.join(f'`{token}`' for token in row['tokens'])} |"
        for row in result["index_metadata_violations"]
    ) or "| - | - |"
    return f"""# v1.6.1 External Test Isolation Audit

## Conclusion

`{result['marker']}`

This audit statically checks that isolated external test set paths are not referenced by code that could build indexes, train models, tune prompts, select fusion weights, or calibrate thresholds. Allowed references are limited to split generation, evaluation, release-gate reporting, and SFT readiness auditing.

## Allowed References

| File | External-test token |
| --- | --- |
{allowed_rows}

## Violations

| File | External-test token | Purpose hint |
| --- | --- | --- |
{violation_rows}

## RAG Index Metadata

| File | External-test token |
| --- | --- |
{index_rows}

## Policy

External test sets may be used only for final evaluation and release-gate reporting. They must not be used for indexing, training, prompt selection, fusion-weight tuning, or threshold calibration.
"""


def main() -> int:
    allowed_references, violations = audit_code_references()
    index_metadata_violations = audit_index_metadata()
    result = {
        "marker": "EXTERNAL_TEST_ISOLATION_AUDIT_PASS"
        if not violations and not index_metadata_violations
        else "EXTERNAL_TEST_ISOLATION_AUDIT_FAIL",
        "allowed_references": allowed_references,
        "violations": violations,
        "index_metadata_violations": index_metadata_violations,
        "policy": {
            "external_test_allowed_for": ["final_evaluation", "release_gate_reporting", "sft_readiness_audit"],
            "external_test_forbidden_for": [
                "indexing",
                "training",
                "prompt_selection",
                "fusion_weight_tuning",
                "threshold_calibration",
            ],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(markdown(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0 if result["marker"].endswith("_PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
