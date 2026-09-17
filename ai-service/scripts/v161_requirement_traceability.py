import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "v161_requirement_traceability.json"
REPORT = ROOT / "docs" / "124_v161_requirement_traceability_matrix.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def exists_all(paths: list[str]) -> bool:
    return all((ROOT / path).exists() for path in paths)


def gate_status(gates: list[dict], name: str, blocked_status: str) -> str:
    row = next((item for item in gates if item.get("name") == name), None)
    if not row:
        return "MISSING"
    return "COMPLETE" if row.get("passed") else blocked_status


def requirement_rows() -> list[dict]:
    final_gate = read_json(ROOT / "data/multimodal/audit/v161_final_gate_results.json")
    gates = final_gate.get("gates", [])
    leakage = read_json(ROOT / "data/rag/audit/leakage_audit_summary.json")
    validity = read_json(ROOT / "data/rag/audit/validity_external_eval_results.json")
    qwen = read_json(ROOT / "data/rag/audit/qwen_realworld_external_eval_results.json")
    vlm = read_json(ROOT / "data/multimodal/eval/vlm_visual_eval_results.json")
    vlm_smoke = read_json(ROOT / "data/multimodal/eval/vlm_provider_smoke_results.json")
    ablation = read_json(ROOT / "data/multimodal/eval/multimodal_ablation_results.json")
    route = read_json(ROOT / "data/multimodal/eval/route_calibration_results.json")
    sft = read_json(ROOT / "data/multimodal/audit/sft_data_readiness.json")
    regression = read_json(ROOT / "data/multimodal/audit/v161_full_regression_results.json")

    real_external_count = validity.get("real_external_count", validity.get("counts", {}).get("real_external", 0))
    multimodal_external_count = vlm.get("external_multimodal_count", 0)
    leakage_complete = (
        leakage.get("exact_duplicate_count") == 0
        and leakage.get("normalized_duplicate_count") == 0
        and leakage.get("bge_m3_cosine_checked") is True
    )
    release_gate_evidence_ready = exists_all(
        [
            "scripts/e-review-v161-full-regression.ps1",
            "scripts/e-review-v161-final-gate.ps1",
            "data/multimodal/audit/v161_final_gate_results.json",
            "docs/121_v161_final_gate_report.md",
        ]
    )
    release_gate_marker = final_gate.get("marker")
    regression_result = regression.get("result")

    return [
        {
            "id": 1,
            "requirement": "Data leakage audit",
            "status": "COMPLETE" if leakage_complete else "INCOMPLETE",
            "evidence": [
                "ai-service/scripts/audit_rag_dataset_leakage.py",
                "scripts/e-review-rag-leakage-audit.ps1",
                "data/rag/audit/leakage_audit_summary.json",
                "docs/108_v161_synthetic_data_leakage_audit.md",
            ],
            "summary": (
                f"exact={leakage.get('exact_duplicate_count')}, "
                f"normalized={leakage.get('normalized_duplicate_count')}, "
                f"near={leakage.get('near_duplicate_count')}, "
                f"metadata_shortcut={leakage.get('metadata_shortcut_count')}"
            ),
        },
        {
            "id": 2,
            "requirement": "Real text data and external test set",
            "status": "BLOCKED",
            "evidence": [
                "data/real_world/source_manifest/source_manifest.jsonl",
                "scripts/e-review-realworld-ingest.ps1",
                "data/rag/audit/validity_external_eval_results.json",
                "data/rag/audit/qwen_realworld_external_eval_results.json",
                "docs/109_v161_real_data_source_and_license_report.md",
                "docs/112_v161_rag_validity_external_eval_report.md",
                "docs/114_v161_qwen_realworld_external_eval_report.md",
            ],
            "summary": (
                f"real_external={real_external_count}, "
                f"rag_marker={validity.get('marker')}, "
                f"qwen_marker={qwen.get('marker')}"
            ),
        },
        {
            "id": 3,
            "requirement": "VLM Provider smoke test",
            "status": gate_status(gates, "vlm_provider_smoke", "BLOCKED"),
            "evidence": [
                "ai-service/app/vlm/",
                "ai-service/app/api/vlm.py",
                "scripts/e-review-vlm-provider-smoke.ps1",
                "data/multimodal/eval/vlm_provider_smoke_results.json",
                "docs/116_v161_vlm_provider_design.md",
                "docs/127_v161_vlm_provider_smoke_report.md",
            ],
            "summary": (
                f"marker={vlm_smoke.get('marker')}, "
                f"model_available={vlm_smoke.get('model_available')}, "
                f"schema_valid={vlm_smoke.get('schema_valid')}"
            ),
        },
        {
            "id": 4,
            "requirement": "Image-text data and annotation standards",
            "status": "COMPLETE_FOR_GUIDELINES_BLOCKED_FOR_REAL_DATA"
            if exists_all(
                [
                    "docs/110_v161_real_review_annotation_guideline.md",
                    "docs/111_v161_multimodal_annotation_guideline.md",
                ]
            )
            else "INCOMPLETE",
            "evidence": [
                "docs/110_v161_real_review_annotation_guideline.md",
                "docs/111_v161_multimodal_annotation_guideline.md",
                "data/real_world/source_manifest/source_manifest.jsonl",
            ],
            "summary": (
                "Annotation guidelines exist; compliant real multimodal samples remain blocked "
                f"with external_multimodal_count={multimodal_external_count}."
            ),
        },
        {
            "id": 5,
            "requirement": "VLM structured visual evidence",
            "status": "COMPLETE_FOR_SCHEMA_BLOCKED_FOR_REAL_INFERENCE"
            if exists_all(
                [
                    "ai-service/app/vlm/schemas.py",
                    "docs/117_v161_visual_schema_and_evidence_boundary.md",
                ]
            )
            else "INCOMPLETE",
            "evidence": [
                "ai-service/app/vlm/schemas.py",
                "ai-service/app/vlm/service.py",
                "scripts/e-review-vlm-visual-eval.ps1",
                "data/multimodal/eval/vlm_visual_eval_results.json",
                "docs/117_v161_visual_schema_and_evidence_boundary.md",
                "docs/128_v161_vlm_visual_evidence_eval_report.md",
                "ai-service/tests/test_vlm_provider.py",
            ],
            "summary": f"schema and evaluator exist; real VLM marker={vlm.get('marker')}",
        },
        {
            "id": 6,
            "requirement": "Multimodal Agent integration",
            "status": "COMPLETE_FOR_REGISTRY_BLOCKED_FOR_REAL_VLM_EXECUTION",
            "evidence": [
                "litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/service/EnterpriseAgentPlatformService.java",
                "docs/118_v161_multimodal_agent_integration_report.md",
                "docs/121_v161_final_gate_report.md",
            ],
            "summary": "Visual tools are represented in the agent evidence boundary; real execution waits for model and data.",
        },
        {
            "id": 7,
            "requirement": "Four-way multimodal ablation evaluation",
            "status": "BLOCKED",
            "evidence": [
                "scripts/e-review-multimodal-ablation-eval.ps1",
                "data/multimodal/eval/multimodal_ablation_results.json",
                "docs/113_v161_multimodal_ablation_eval_report.md",
            ],
            "summary": f"all four modes are reported with null metrics while marker={ablation.get('marker')}",
        },
        {
            "id": 8,
            "requirement": "Human review routing calibration",
            "status": gate_status(gates, "route_calibration", "BLOCKED"),
            "evidence": [
                "ai-service/app/metrics/human_review.py",
                "scripts/e-review-multimodal-route-calibration.ps1",
                "data/multimodal/eval/route_calibration_results.json",
                "docs/119_v161_multimodal_route_calibration_report.md",
            ],
            "summary": (
                f"synthetic unsafe_auto_pass="
                f"{route.get('synthetic_label_policy_sanity_check', {}).get('unsafe_auto_pass_rate')}; "
                f"marker={route.get('marker')}"
            ),
        },
        {
            "id": 9,
            "requirement": "SFT data readiness audit",
            "status": "BLOCKED",
            "evidence": [
                "ai-service/scripts/audit_sft_data_readiness.py",
                "data/multimodal/audit/sft_data_readiness.json",
                "docs/115_v161_sft_data_readiness_report.md",
            ],
            "summary": f"text={sft.get('sft_status')}, vlm={sft.get('vlm_sft_status')}",
        },
        {
            "id": 10,
            "requirement": "Full regression and release gate",
            "status": "COMPLETE_WITH_BLOCKED_RELEASE_GATES"
            if release_gate_evidence_ready and release_gate_marker in {"V161_FINAL_GATE_BLOCKED", "V161_FINAL_GATE_PASS"}
            else "INCOMPLETE",
            "evidence": [
                "scripts/e-review-v161-full-regression.ps1",
                "scripts/e-review-v161-final-gate.ps1",
                "data/multimodal/audit/v161_full_regression_results.json",
                "data/multimodal/audit/v161_final_gate_results.json",
                "docs/121_v161_final_gate_report.md",
                "docs/122_v161_full_regression_report.md",
                "docs/123_v161_build_regression_report.md",
            ],
            "summary": (
                f"final_gate={release_gate_marker}, release_allowed={final_gate.get('release_allowed')}, "
                f"last_regression_result={regression_result}"
            ),
        },
    ]


def markdown(rows: list[dict]) -> str:
    lines = [
        "# v1.6.1 Requirement Traceability Matrix",
        "",
        "## Conclusion",
        "",
        (
            "This matrix maps the active 10-item v1.6.1 objective to the current "
            "evidence. `BLOCKED` means the evidence is intentionally not treated as "
            "completion and must not be used to justify a release tag."
        ),
        "",
        "| ID | Objective | Status | Evidence | Summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        evidence = "<br>".join(f"`{item}`" for item in row["evidence"])
        lines.append(f"| {row['id']} | {row['requirement']} | `{row['status']}` | {evidence} | {row['summary']} |")
    lines.extend(
        [
            "",
            "## Release Decision",
            "",
            (
                "The branch has audit scripts, schema plumbing, blocked-state reports, "
                "and regression evidence. It still lacks the repo-external compliant "
                "real text dataset, compliant real multimodal dataset, local VLM weights, "
                "real multimodal ablation metrics, and real routing calibration evidence. "
                "Keep `V161_FINAL_GATE_BLOCKED`; do not create the "
                "`v1.6.1-realworld-multimodal-evaluation` release tag."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    rows = requirement_rows()
    result = {
        "marker": "V161_REQUIREMENT_TRACEABILITY_COMPLETE",
        "release_allowed": False,
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(markdown(rows), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
