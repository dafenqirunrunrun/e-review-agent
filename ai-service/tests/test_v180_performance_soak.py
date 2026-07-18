import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ai-service/scripts/run_v180_performance_soak.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_v180_performance_soak", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v180_performance_smoke_does_not_claim_90_min_soak():
    result = load_module().run_soak(duration_seconds=1, target_rps=2)
    assert result["status"] == "V180_PERFORMANCE_SMOKE_PASS_SOAK_PENDING"
    assert result["soak_90_min_completed"] is False
    assert result["success_rate"] >= 0.99


def test_v180_performance_soak_artifact_records_completed_90_min_gate():
    artifact = json.loads((ROOT / "data/private_research/audit/v180_performance_soak.json").read_text(encoding="utf-8"))
    assert artifact["status"] == "V180_90_MIN_SOAK_PASS"
    assert artifact["soak_90_min_required"] is True
    assert artifact["soak_90_min_completed"] is True
    assert artifact["duration_seconds"] >= 5400
    assert artifact["request_count"] >= 10000
    assert artifact["success_rate"] == 1.0
