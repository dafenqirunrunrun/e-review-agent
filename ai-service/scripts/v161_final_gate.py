import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "v161_final_gate_results.json"
REPORT = ROOT / "docs" / "121_v161_final_gate_report.md"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def git_ls_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def check_forbidden_git_files(files: list[str]) -> list[str]:
    forbidden_parts = [
        "__pycache__/",
        ".pytest_cache/",
        "huggingface/",
        ".cache/huggingface/",
        "data/real_world/raw_private/",
        "data-private/",
    ]
    forbidden_suffixes = [
        ".safetensors",
        ".bin",
        ".pt",
        ".pth",
        ".ckpt",
        ".onnx",
        ".gguf",
        ".faiss",
    ]
    matches = []
    for file_name in files:
        lowered = file_name.lower()
        is_private_env = lowered.endswith("/.env") or lowered == ".env"
        if is_private_env or any(part in lowered for part in forbidden_parts) or any(
            lowered.endswith(suffix) for suffix in forbidden_suffixes
        ):
            matches.append(file_name)
    return matches


def gate(name: str, status: str, expected: str, evidence: str, release_required: bool = True) -> dict:
    passed = status == expected
    return {
        "name": name,
        "status": status,
        "expected_for_release": expected,
        "passed": passed,
        "release_required": release_required,
        "evidence": evidence,
    }


def format_table(rows: list[dict]) -> str:
    lines = ["| Gate | Current | Required | Release gate | Evidence |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        release_gate = "yes" if row["release_required"] else "no"
        lines.append(
            f"| {row['name']} | `{row['status']}` | `{row['expected_for_release']}` | {release_gate} | {row['evidence']} |"
        )
    return "\n".join(lines)


def report_text(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["release_blockers"]) or "- none"
    return f"""# v1.6.1 Final Gate Report

## Conclusion

`{result['marker']}`

- Release allowed: `{result['release_allowed']}`
- Recommended tag: `{result['recommended_tag']}`
- Git forbidden tracked files: `{len(result['forbidden_git_files'])}`

## Gate Details

{format_table(result['gates'])}

## Release Blockers

{blockers}

## Key Metrics

- exact duplicate count: `{result['metrics']['exact_duplicate_count']}`
- normalized duplicate count: `{result['metrics']['normalized_duplicate_count']}`
- near duplicate count: `{result['metrics']['near_duplicate_count']}`
- metadata shortcut count: `{result['metrics']['metadata_shortcut_count']}`
- strict no-oracle Hit@5: `{result['metrics']['strict_no_oracle_hit5']}`
- real external count: `{result['metrics']['real_external_count']}`
- qwen real external count: `{result['metrics']['qwen_real_external_count']}`
- VLM provider model available: `{result['metrics']['vlm_provider_model_available']}`
- multimodal external count: `{result['metrics']['multimodal_external_count']}`
- route unsafe auto pass rate: `{result['metrics']['route_unsafe_auto_pass_rate']}`
- route high risk review recall: `{result['metrics']['route_high_risk_review_recall']}`

## Release Decision

The current artifacts can be used as v1.6.1 audit and multimodal integration
preparation evidence, but they cannot be released as a completed real-world
external evaluation version. The release tag `v1.6.1-realworld-multimodal-evaluation`
is allowed only after all required release gates pass.
"""


def main() -> int:
    leakage = read_json(ROOT / "data/rag/audit/leakage_audit_summary.json")
    validity = read_json(ROOT / "data/rag/audit/validity_external_eval_results.json")
    qwen_realworld = read_json(ROOT / "data/rag/audit/qwen_realworld_external_eval_results.json")
    vlm_smoke = read_json(ROOT / "data/multimodal/eval/vlm_provider_smoke_results.json")
    vlm = read_json(ROOT / "data/multimodal/eval/vlm_visual_eval_results.json")
    ablation = read_json(ROOT / "data/multimodal/eval/multimodal_ablation_results.json")
    route = read_json(ROOT / "data/multimodal/eval/route_calibration_results.json")
    sft = read_json(ROOT / "data/multimodal/audit/sft_data_readiness.json")
    manifest = read_jsonl(ROOT / "data/real_world/source_manifest/source_manifest.jsonl")
    tracked_files = git_ls_files()
    forbidden = check_forbidden_git_files(tracked_files)

    leakage_complete = (
        bool(leakage)
        and leakage.get("exact_duplicate_count") == 0
        and leakage.get("normalized_duplicate_count") == 0
        and leakage.get("bge_m3_cosine_checked") is True
    )
    strict_hit5 = (
        validity.get("strict_no_oracle", {})
        .get("hybrid_rerank", {})
        .get("hit_at_5")
    )
    real_external_count = validity.get("real_external_count", validity.get("counts", {}).get("real_external", 0))
    qwen_real_external_count = qwen_realworld.get("real_external_count", 0)
    vlm_provider_model_available = vlm_smoke.get("model_available")
    multimodal_external_count = vlm.get("external_multimodal_count", 0)
    route_metrics = route.get("synthetic_label_policy_sanity_check") or {}

    gates = [
        gate(
            "synthetic_leakage_audit",
            "RAG_LEAKAGE_AUDIT_COMPLETE" if leakage_complete else "MISSING_OR_FAILED",
            "RAG_LEAKAGE_AUDIT_COMPLETE",
            "data/rag/audit/leakage_audit_summary.json",
            False,
        ),
        gate(
            "source_manifest",
            "SOURCE_MANIFEST_PRESENT" if len(manifest) >= 1 else "SOURCE_MANIFEST_MISSING",
            "SOURCE_MANIFEST_PRESENT",
            "data/real_world/source_manifest/source_manifest.jsonl",
            False,
        ),
        gate(
            "realworld_external_eval",
            validity.get("marker", "MISSING"),
            "REALWORLD_EXTERNAL_EVAL_PASS",
            "data/rag/audit/validity_external_eval_results.json",
        ),
        gate(
            "qwen_realworld_external_eval",
            qwen_realworld.get("marker", "MISSING"),
            "REALWORLD_QWEN_EXTERNAL_EVAL_PASS",
            "data/rag/audit/qwen_realworld_external_eval_results.json",
        ),
        gate(
            "vlm_provider_smoke",
            vlm_smoke.get("marker", "MISSING"),
            "VLM_PROVIDER_SMOKE_PASS",
            "data/multimodal/eval/vlm_provider_smoke_results.json",
        ),
        gate(
            "multimodal_vlm_eval",
            vlm.get("marker", "MISSING"),
            "MULTIMODAL_VLM_EVAL_PASS",
            "data/multimodal/eval/vlm_visual_eval_results.json",
        ),
        gate(
            "multimodal_ablation_eval",
            ablation.get("marker", "MISSING"),
            "MULTIMODAL_ABLATION_EVAL_PASS",
            "data/multimodal/eval/multimodal_ablation_results.json",
        ),
        gate(
            "route_calibration",
            route.get("marker", "MISSING"),
            "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_PASS",
            "data/multimodal/eval/route_calibration_results.json",
        ),
        gate(
            "text_sft_readiness",
            sft.get("sft_status", "MISSING"),
            "SFT_DATA_READY",
            "data/multimodal/audit/sft_data_readiness.json",
        ),
        gate(
            "vlm_sft_readiness",
            sft.get("vlm_sft_status", "MISSING"),
            "VLM_SFT_DATA_READY",
            "data/multimodal/audit/sft_data_readiness.json",
        ),
        gate(
            "forbidden_git_payload",
            "NO_FORBIDDEN_TRACKED_PAYLOAD" if not forbidden else "FORBIDDEN_TRACKED_PAYLOAD_FOUND",
            "NO_FORBIDDEN_TRACKED_PAYLOAD",
            "git ls-files",
        ),
    ]
    release_blockers = [
        f"{row['name']}: current={row['status']}, required={row['expected_for_release']}"
        for row in gates
        if row["release_required"] and not row["passed"]
    ]
    release_allowed = not release_blockers
    result = {
        "marker": "V161_FINAL_GATE_PASS" if release_allowed else "V161_FINAL_GATE_BLOCKED",
        "release_allowed": release_allowed,
        "recommended_tag": "v1.6.1-realworld-multimodal-evaluation" if release_allowed else None,
        "gates": gates,
        "release_blockers": release_blockers,
        "forbidden_git_files": forbidden,
        "metrics": {
            "exact_duplicate_count": leakage.get("exact_duplicate_count"),
            "normalized_duplicate_count": leakage.get("normalized_duplicate_count"),
            "near_duplicate_count": leakage.get("near_duplicate_count"),
            "metadata_shortcut_count": leakage.get("metadata_shortcut_count"),
            "strict_no_oracle_hit5": strict_hit5,
            "real_external_count": real_external_count,
            "qwen_real_external_count": qwen_real_external_count,
            "vlm_provider_model_available": vlm_provider_model_available,
            "multimodal_external_count": multimodal_external_count,
            "route_unsafe_auto_pass_rate": route_metrics.get("unsafe_auto_pass_rate"),
            "route_high_risk_review_recall": route_metrics.get("high_risk_review_recall"),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
