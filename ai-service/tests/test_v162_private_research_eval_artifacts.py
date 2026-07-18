import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


def run_script(name: str, *args: str) -> str:
    completed = subprocess.run(
        [PYTHON, str(ROOT / "ai-service" / "scripts" / name), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout


def load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_private_text_exploratory_artifact_is_not_formal_benchmark():
    run_script(
        "eval_private_real_text_exploratory.py",
        "--per-source",
        "0",
        "--stability-per-source",
        "0",
        "--blocked-reason",
        "pytest_artifact_validation",
        "--attempted-smoke-per-source",
        "1",
        "--attempted-smoke-status",
        "aborted_due_latency",
    )

    summary = load_json("data/private_research/eval/private_text_exploratory_summary.json")
    manifest = load_json("data/private_research/eval/private_text_exploratory_manifest.json")

    assert summary["marker"] == "PRIVATE_TEXT_EXPLORATORY_BASELINE_FAIL"
    assert summary["project_mode"] == "private_noncommercial_research"
    assert summary["private_exploratory"] is True
    assert summary["formal_benchmark"] is False
    assert summary["publication_ready"] is False
    assert summary["contains_gold_labels"] is False
    assert summary["macro_f1_calculated"] is False
    assert summary["visual_evidence_generated"] is False
    assert summary["attempted_smoke_status"] == "aborted_due_latency"
    metric_text = json.dumps(summary["prompt_only"]) + json.dumps(summary["rag"]) + json.dumps(summary["comparison"])
    assert "macro_f1" not in metric_text.lower()
    assert manifest["raw_text_in_git"] is False
    assert manifest["full_model_output_in_git"] is False


def test_private_text_exploratory_metrics_do_not_claim_success_without_real_model_runs():
    summary = load_json("data/private_research/eval/private_text_exploratory_summary.json")

    assert summary["prompt_only"]["input_record_count"] == 0
    assert summary["rag"]["input_record_count"] == 0
    assert summary["prompt_only"]["real_model_inference_count"] == 0
    assert summary["rag"]["real_model_inference_count"] == 0
    assert summary["prompt_only"]["fallback_rate"] == 1.0
    assert summary["rag"]["fallback_rate"] == 1.0
    assert summary["comparison"]["latency_delta"] is None


def test_synthetic_sft_readiness_is_engineering_only_and_project_owned():
    stdout = run_script("audit_private_synthetic_sft_readiness.py")
    assert "PRIVATE_SYNTHETIC_SFT_ENGINEERING_READY" in stdout

    readiness = load_json("data/private_research/audit/synthetic_sft_readiness.json")

    assert readiness["marker"] == "PRIVATE_SYNTHETIC_SFT_ENGINEERING_READY"
    assert readiness["source_type"] == "synthetic_project_owned"
    assert readiness["contains_amazon_text"] is False
    assert readiness["contains_asap_text"] is False
    assert readiness["contains_public_pilot_images"] is False
    assert readiness["contains_authorized_external_test"] is False
    assert sum(readiness["contains_pii_counts"].values()) == 0
    assert readiness["engineering_smoke_ready_only"] is True
    assert readiness["weight_publication_allowed"] is False
    assert readiness["realworld_performance_claim_allowed"] is False
