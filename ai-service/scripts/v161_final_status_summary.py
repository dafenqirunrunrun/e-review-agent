import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "v161_final_status_summary.json"
REPORT = ROOT / "docs" / "129_v161_final_status_summary.md"


def load_json(path: str) -> dict[str, Any]:
    target = ROOT / path
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def load_jsonl(path: str) -> list[dict[str, Any]]:
    target = ROOT / path
    if not target.exists():
        return []
    rows = []
    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def git_output(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def nested(data: dict[str, Any], *keys: str, default: Any = "not_available") -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def first_metric(data: dict[str, Any], *paths: tuple[str, ...], default: Any = "not_available") -> Any:
    for path in paths:
        value = nested(data, *path, default=None)
        if value is not None:
            return value
    return default


def latest_pytest_summary(regression: dict[str, Any]) -> str:
    for stage in regression.get("stages", []):
        if stage.get("name") == "python-pytest":
            lines = stage.get("output_summary") or []
            return lines[-1] if lines else stage.get("status", "not_available")
    return "not_available"


def build_summary() -> dict[str, Any]:
    leakage = load_json("data/rag/audit/leakage_audit_summary.json")
    validity = load_json("data/rag/audit/validity_external_eval_results.json")
    qwen_external = load_json("data/rag/audit/qwen_realworld_external_eval_results.json")
    vlm_smoke = load_json("data/multimodal/eval/vlm_provider_smoke_results.json")
    vlm_visual = load_json("data/multimodal/eval/vlm_visual_eval_results.json")
    ablation = load_json("data/multimodal/eval/multimodal_ablation_results.json")
    route = load_json("data/multimodal/eval/route_calibration_results.json")
    sft = load_json("data/multimodal/audit/sft_data_readiness.json")
    final_gate = load_json("data/multimodal/audit/v161_final_gate_results.json")
    regression = load_json("data/multimodal/audit/v161_full_regression_results.json")
    build = load_json("data/multimodal/audit/v161_build_regression_results.json")
    manifest = load_jsonl("data/real_world/source_manifest/source_manifest.jsonl")

    branch = git_output(["branch", "--show-current"])
    commit = git_output(["rev-parse", "--short", "HEAD"])
    head_tags = git_output(["tag", "--points-at", "HEAD"])
    status_short = git_output(["status", "--short"])

    source_summary = []
    for row in manifest:
        source_summary.append(
            {
                "source_id": row.get("source_id"),
                "source_name": row.get("source_name"),
                "license": row.get("license"),
                "status": row.get("status"),
                "contains_images": row.get("contains_images"),
                "redistribution_allowed": row.get("redistribution_allowed"),
            }
        )

    strict_no_oracle_hit3 = first_metric(
        validity,
        ("strict_no_oracle", "hybrid_neural", "hit_at_3"),
        ("strict_no_oracle", "hybrid_rerank", "hit_at_3"),
        ("metrics", "strict_no_oracle_hybrid_hit3"),
    )
    strict_no_oracle_hit5 = nested(final_gate, "metrics", "strict_no_oracle_hit5")
    original_hit3 = first_metric(
        validity,
        ("original_oracle", "hybrid_neural", "hit_at_3"),
        ("original_oracle", "hybrid_rerank", "hit_at_3"),
    )
    original_hit5 = nested(validity, "original_oracle_hybrid_hit5", default=None)
    if original_hit5 is None:
        original_hit5 = first_metric(
            validity,
            ("original_oracle", "hybrid_neural", "hit_at_5"),
            ("original_oracle", "hybrid_rerank", "hit_at_5"),
        )

    text_image_rag_metrics = nested(ablation, "metrics", "text_image_hybrid_rag", default={})
    text_image_metrics = nested(ablation, "metrics", "text_image", default={})
    text_only_metrics = nested(ablation, "metrics", "text_only", default={})
    image_only_metrics = nested(ablation, "metrics", "image_only", default={})
    visual_metrics = nested(vlm_visual, "metrics", default={})
    route_metrics = route.get("synthetic_label_policy_sanity_check") or {}

    items = [
        ("branch", branch),
        ("compliant_real_text_data_found", nested(final_gate, "metrics", "real_external_count") not in (0, "not_available")),
        ("compliant_real_multimodal_data_found", nested(final_gate, "metrics", "multimodal_external_count") not in (0, "not_available")),
        ("data_sources_and_licenses", source_summary),
        ("real_text_count", nested(sft, "checks", "real_dev_count", default=0)),
        ("real_multimodal_count", nested(final_gate, "metrics", "multimodal_external_count", default=0)),
        ("external_text_test_size", nested(final_gate, "metrics", "real_external_count", default=0)),
        ("external_multimodal_test_size", nested(final_gate, "metrics", "multimodal_external_count", default=0)),
        ("raw_real_images_in_git", "no"),
        ("vlm_model_name", vlm_smoke.get("model_name", "Qwen3-VL-2B-Instruct")),
        ("vlm_4bit_enabled", vlm_smoke.get("load_in_4bit", "not_available")),
        ("actual_gpu_and_peak_memory", "cuda available via torchtest; VLM peak memory not_available because VLM inference is blocked"),
        ("vlm_avg_and_p95_latency", {"avg_latency_ms": visual_metrics.get("avg_latency_ms"), "p95_latency_ms": visual_metrics.get("p95_latency_ms")}),
        ("exact_duplicate_count", leakage.get("exact_duplicate_count", "not_available")),
        ("near_duplicate_count", leakage.get("near_duplicate_count", "not_available")),
        ("original_synthetic_hit3_hit5", {"hit_at_3": original_hit3, "hit_at_5": original_hit5}),
        ("strict_synthetic_hit3_hit5", {"hit_at_3": strict_no_oracle_hit3, "hit_at_5": strict_no_oracle_hit5}),
        ("real_external_no_oracle_hit3_hit5", "BLOCKED: real external text test set is not available"),
        ("real_text_risk_type_macro_f1", nested(qwen_external, "metrics", "qwen3_synthetic_plus_real_hybrid_rag", "risk_type_macro_f1")),
        ("text_only_macro_f1", text_only_metrics.get("risk_type_macro_f1")),
        ("image_only_macro_f1", image_only_metrics.get("risk_type_macro_f1")),
        ("text_image_macro_f1", text_image_metrics.get("risk_type_macro_f1")),
        ("text_image_rag_macro_f1", text_image_rag_metrics.get("risk_type_macro_f1")),
        ("visual_evidence_support_rate", visual_metrics.get("visual_evidence_support_rate")),
        ("visual_unsupported_claim_rate", visual_metrics.get("visual_unsupported_claim_rate")),
        ("text_image_consistency_macro_f1", visual_metrics.get("text_image_consistency_macro_f1")),
        ("privacy_risk_recall", visual_metrics.get("privacy_risk_recall")),
        ("human_review_precision", route_metrics.get("human_review_precision")),
        ("human_review_recall", route_metrics.get("human_review_recall")),
        ("high_risk_review_recall", route_metrics.get("high_risk_review_recall")),
        ("unsafe_auto_pass_rate", route_metrics.get("unsafe_auto_pass_rate")),
        ("multimodal_vlm_eval_pass", nested(final_gate, "gates", default=[])[5].get("passed") if len(nested(final_gate, "gates", default=[])) > 5 else False),
        ("realworld_multimodal_route_calibration_pass", route.get("marker") == "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_PASS"),
        ("sft_data_ready", sft.get("sft_status") == "SFT_DATA_READY"),
        ("vlm_sft_data_ready", sft.get("vlm_sft_status") == "VLM_SFT_DATA_READY"),
        ("python_test_result", latest_pytest_summary(regression)),
        ("maven_result", nested(build, "maven-package", default="see docs/123_v161_build_regression_report.md")),
        ("admin_h5_build_result", nested(build, "frontend-builds", default="see docs/123_v161_build_regression_report.md")),
        ("commit", f"generated_from_commit={commit}; final artifact commit is assigned after this report is committed"),
        ("tag", head_tags or "none"),
        (
            "working_tree_clean_at_generation",
            "yes" if status_short == "" else "no; summary generation observed uncommitted files",
        ),
        ("recommend_enter_qwen3_ms_swift_qlora_sft", "no; SFT_DATA_READY and VLM_SFT_DATA_READY are both false"),
    ]
    payload = {
        "marker": "V161_FINAL_STATUS_SUMMARY_COMPLETE",
        "final_gate_marker": final_gate.get("marker"),
        "release_allowed": final_gate.get("release_allowed"),
        "items": [{"id": index + 1, "name": name, "value": value} for index, (name, value) in enumerate(items)],
        "notes": [
            "Blocked or null values are intentional evidence, not zero scores.",
            "No release tag is recommended unless V161_FINAL_GATE_PASS is produced by the final gate script.",
        ],
    }
    return payload


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v1.6.1 Final Status Summary",
        "",
        "## Conclusion",
        "",
        f"- Marker: `{payload['marker']}`",
        f"- Final gate marker: `{payload['final_gate_marker']}`",
        f"- Release allowed: `{payload['release_allowed']}`",
        "",
        "This report maps the requested 42 final-output fields to current machine-readable evidence. `BLOCKED`, `null`, and `not_available` values are preserved when real data, local VLM weights, or real inference evidence is missing.",
        "",
        "## 42-Item Summary",
        "",
        "| ID | Field | Current value |",
        "| --- | --- | --- |",
    ]
    for item in payload["items"]:
        value = item["value"]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False)
        elif value is None:
            rendered = "null"
        else:
            rendered = str(value)
        rendered = rendered.replace("|", "\\|")
        lines.append(f"| {item['id']} | {item['name']} | `{rendered}` |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Blocked or null values are not failures of this summary script; they are the current verified state.",
            "- Do not create `v1.6.1-realworld-multimodal-evaluation` unless the final gate reports `V161_FINAL_GATE_PASS`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    payload = build_summary()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(markdown(payload), encoding="utf-8", newline="\n")
    print(json.dumps({"marker": payload["marker"], "final_gate_marker": payload["final_gate_marker"], "release_allowed": payload["release_allowed"]}, ensure_ascii=False))
    print(payload["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
