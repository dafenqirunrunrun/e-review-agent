import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "v161_full_regression_results.json"
REPORT = ROOT / "docs" / "122_v161_full_regression_report.md"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_stage(name, command, expected_markers=None, expected_blocked_markers=None, cwd=None, env=None):
    expected_markers = expected_markers or []
    expected_blocked_markers = expected_blocked_markers or []
    started = time.time()
    print(f"==== {name} ====")
    completed = subprocess.run(
        command,
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    sys.stdout.write(output.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    found = [marker for marker in expected_markers + expected_blocked_markers if marker in output]
    missing = [marker for marker in expected_markers if marker not in found]
    status = "PASS" if completed.returncode == 0 and not missing else "FAIL"
    error = None
    if completed.returncode != 0:
        error = f"exit_code={completed.returncode}"
    elif missing:
        error = "missing expected marker(s): " + ", ".join(missing)
    return {
        "name": name,
        "status": status,
        "duration_seconds": round(time.time() - started, 2),
        "return_code": completed.returncode,
        "found_markers": found,
        "expected_markers": expected_markers,
        "expected_blocked_markers": expected_blocked_markers,
        "error": error,
        "output_summary": summarize_output(output, found),
    }


def powershell_script(script_name, *args):
    return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / script_name), *args]


def summarize_output(output, found_markers):
    useful_fragments = [
        "passed",
        "skipped",
        "BUILD SUCCESS",
        "compiled successfully",
        "RAG_LEAKAGE_AUDIT_COMPLETE",
        "EXTERNAL_TEST_ISOLATION_AUDIT_PASS",
        "V161_UNBLOCK_PREREQUISITES_BLOCKED",
        "V161_UNBLOCK_PREREQUISITES_READY",
        "PUBLIC_REAL_DATA_LOCAL_SOURCE_BLOCKED",
        "REALWORLD_SPLIT_BLOCKED",
        "REALWORLD_EXTERNAL_EVAL_BLOCKED",
        "MULTIMODAL_VLM_EVAL_BLOCKED",
        "VLM_OBSERVABILITY_BLOCKED",
        "MULTIMODAL_ABLATION_EVAL_BLOCKED",
        "VLM_PROVIDER_SMOKE_BLOCKED",
        "REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED",
        "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED",
        "SFT_DATA_NOT_READY",
        "VLM_SFT_DATA_NOT_READY",
        "SECURITY_HYGIENE_CHECK_PASS",
        "DOC_LINK_CHECK_PASS",
        "ENCODING_CHECK_PASS",
        "ERROR_MESSAGE_CHECK_PASS",
        "V161_FINAL_GATE_BLOCKED",
        "V161_FINAL_STATUS_SUMMARY_COMPLETE",
    ]
    lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "\ufffd" in stripped or "\x1b" in stripped:
            continue
        if any(fragment in stripped for fragment in useful_fragments) or any(marker in stripped for marker in found_markers):
            lines.append(stripped)
    return lines[-12:]


def markdown(summary):
    lines = [
        "# v1.6.1 Full Regression Report",
        "",
        "## Conclusion",
        "",
        f"- Regression result: `{summary['result']}`",
        f"- Final gate marker: `{summary['final_gate_marker']}`",
        f"- Release allowed: `{summary['release_allowed']}`",
        f"- Skip builds: `{summary['skip_builds']}`",
        "",
        "## Stage Results",
        "",
        "| Stage | Status | Markers | Duration(s) |",
        "| --- | --- | --- | --- |",
    ]
    for stage in summary["stages"]:
        markers = ", ".join(stage["found_markers"]) if stage["found_markers"] else "-"
        lines.append(f"| {stage['name']} | `{stage['status']}` | {markers} | {stage['duration_seconds']} |")
    lines.extend(
        [
            "",
            "## Release Decision",
            "",
            (
                "This regression proves that the audit and evaluation scripts can run "
                "repeatably and collect the current evidence. Release eligibility is "
                "decided only by `scripts/e-review-v161-final-gate.ps1`. The current "
                "state must not receive the `v1.6.1-realworld-multimodal-evaluation` "
                "release tag unless the final gate reports `V161_FINAL_GATE_PASS`."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_summary(summary):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(markdown(summary), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--torch-python", default="")
    parser.add_argument("--skip-builds", action="store_true")
    parser.add_argument("--reranker-model-dir", default=r"D:\EReviewAgent\models\rag-reranker")
    parser.add_argument("--embedding-device", default="cuda")
    parser.add_argument("--reranker-device", default="cuda")
    parser.add_argument("--real-json", default="")
    parser.add_argument("--vlm-candidates", default="")
    parser.add_argument("--text-model-dirs", default="")
    args = parser.parse_args()

    py = args.python
    rag_py = args.torch_python or py
    env = os.environ.copy()
    env["E_REVIEW_RERANKER_MODEL_DIR"] = args.reranker_model_dir
    env["E_REVIEW_RERANKER_DEVICE"] = args.reranker_device
    env["E_REVIEW_EMBEDDING_DEVICE"] = args.embedding_device

    unblock_args = ["-Python", py]
    if args.real_json:
        unblock_args.extend(["-RealJson", args.real_json])
    if args.vlm_candidates:
        unblock_args.extend(["-VlmCandidates", args.vlm_candidates])
    if args.text_model_dirs:
        unblock_args.extend(["-TextModelDirs", args.text_model_dirs])
    if args.torch_python:
        unblock_args.extend(["-TorchPython", args.torch_python])

    stages = [
        run_stage("python-pytest", [py, "-m", "pytest"], cwd=ROOT / "ai-service"),
        run_stage("unblock-prerequisites", powershell_script("e-review-v161-unblock-prerequisites.ps1", *unblock_args), [], ["V161_UNBLOCK_PREREQUISITES_BLOCKED"]),
        run_stage("external-test-isolation", powershell_script("e-review-external-test-isolation-audit.ps1", "-Python", py), ["EXTERNAL_TEST_ISOLATION_AUDIT_PASS"]),
        run_stage("rag-leakage-audit", powershell_script("e-review-rag-leakage-audit.ps1", "-Python", rag_py), ["RAG_LEAKAGE_AUDIT_COMPLETE"], env=env),
        run_stage("realworld-ingest", powershell_script("e-review-realworld-ingest.ps1", "-Python", py), [], ["PUBLIC_REAL_DATA_LOCAL_SOURCE_BLOCKED", "REALWORLD_SPLIT_BLOCKED"]),
        run_stage("rag-validity-external", powershell_script("e-review-rag-validity-external-eval.ps1", "-Python", rag_py), [], ["REALWORLD_EXTERNAL_EVAL_BLOCKED"], env=env),
        run_stage("vlm-provider-smoke", powershell_script("e-review-vlm-provider-smoke.ps1", "-Python", py), [], ["VLM_PROVIDER_SMOKE_BLOCKED"]),
        run_stage("local-vlm-smoke", powershell_script("e-review-local-vlm-smoke.ps1", "-Python", rag_py), [], ["VLM_PROVIDER_SMOKE_BLOCKED"]),
        run_stage("vlm-observability", powershell_script("e-review-vlm-observability.ps1", "-Python", py), [], ["VLM_OBSERVABILITY_BLOCKED"]),
        run_stage("vlm-visual-eval", powershell_script("e-review-vlm-visual-eval.ps1", "-Python", py), [], ["MULTIMODAL_VLM_EVAL_BLOCKED"]),
        run_stage("multimodal-ablation", powershell_script("e-review-multimodal-ablation-eval.ps1", "-Python", py), [], ["MULTIMODAL_ABLATION_EVAL_BLOCKED"]),
        run_stage("qwen-realworld-external", powershell_script("e-review-qwen-realworld-external-eval.ps1", "-Python", py), [], ["REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED"]),
        run_stage("route-calibration", powershell_script("e-review-multimodal-route-calibration.ps1", "-Python", py), [], ["REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED"]),
        run_stage("sft-readiness", [py, str(ROOT / "ai-service" / "scripts" / "audit_sft_data_readiness.py")], [], ["SFT_DATA_NOT_READY", "VLM_SFT_DATA_NOT_READY"]),
        run_stage("security-hygiene", powershell_script("e-review-security-hygiene-check.ps1"), ["SECURITY_HYGIENE_CHECK_PASS"]),
        run_stage("doc-link", powershell_script("e-review-doc-link-check.ps1"), ["DOC_LINK_CHECK_PASS"]),
        run_stage("encoding", powershell_script("e-review-encoding-check.ps1"), ["ENCODING_CHECK_PASS"]),
        run_stage("error-message", powershell_script("e-review-error-message-check.ps1"), ["ERROR_MESSAGE_CHECK_PASS"]),
    ]
    if not args.skip_builds:
        stages.extend(
            [
                run_stage("maven-package", ["mvn", "-DskipTests", "package"]),
                run_stage("admin-build-prod", ["npm", "run", "build:prod"], cwd=ROOT / "litemall-admin"),
                run_stage("h5-build-prod", ["npm", "run", "build:prod"], cwd=ROOT / "litemall-vue"),
            ]
        )
    stages.append(run_stage("v161-final-gate", powershell_script("e-review-v161-final-gate.ps1", "-Python", py), [], ["V161_FINAL_GATE_BLOCKED"]))
    final_gate = json.loads((ROOT / "data" / "multimodal" / "audit" / "v161_final_gate_results.json").read_text(encoding="utf-8"))
    failed = [stage for stage in stages if stage["status"] != "PASS"]
    summary = {
        "result": "FAIL" if failed else "V161_REGRESSION_COMPLETE_WITH_BLOCKED_RELEASE_GATES",
        "final_gate_marker": final_gate.get("marker"),
        "release_allowed": final_gate.get("release_allowed"),
        "skip_builds": args.skip_builds,
        "stages": stages,
    }
    write_summary(summary)

    stages.append(run_stage("final-status-summary", powershell_script("e-review-v161-final-status-summary.ps1", "-Python", py), ["V161_FINAL_STATUS_SUMMARY_COMPLETE"]))
    failed = [stage for stage in stages if stage["status"] != "PASS"]
    summary = {
        "result": "FAIL" if failed else "V161_REGRESSION_COMPLETE_WITH_BLOCKED_RELEASE_GATES",
        "final_gate_marker": final_gate.get("marker"),
        "release_allowed": final_gate.get("release_allowed"),
        "skip_builds": args.skip_builds,
        "stages": stages,
    }
    write_summary(summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
