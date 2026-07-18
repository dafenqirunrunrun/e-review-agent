import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v180_failure_injection_script_passes_25_cases():
    result = subprocess.run(
        [sys.executable, "ai-service/scripts/run_v180_failure_injection.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "V180_FAILURE_INJECTION_25_PASS" in result.stdout


def test_v180_failure_injection_artifact_has_no_failed_cases():
    artifact = json.loads((ROOT / "data/private_research/audit/v180_failure_injection.json").read_text(encoding="utf-8"))
    assert artifact["status"] == "V180_FAILURE_INJECTION_25_PASS"
    assert artifact["case_count"] >= 25
    assert artifact["pass_count"] == artifact["case_count"]
    assert artifact["fail_count"] == 0
    assert artifact["closed_holdout_accessed"] is False
    assert artifact["training_executed"] is False
