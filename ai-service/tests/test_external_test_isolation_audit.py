import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ai-service/scripts/audit_external_test_isolation.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("audit_external_test_isolation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_external_test_isolation_audit_passes_current_codebase():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert "EXTERNAL_TEST_ISOLATION_AUDIT_PASS" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/audit/external_test_isolation_audit.json").read_text(encoding="utf-8"))
    assert result["marker"] == "EXTERNAL_TEST_ISOLATION_AUDIT_PASS"
    assert result["violations"] == []
    assert result["index_metadata_violations"] == []


def test_external_test_isolation_detects_forbidden_reference(tmp_path, monkeypatch):
    module = load_script_module()
    fake_root = tmp_path
    forbidden = fake_root / "ai-service" / "scripts" / "train_with_external.py"
    forbidden.parent.mkdir(parents=True)
    forbidden.write_text(
        "DATA='data/real_world/external_test/real_reviews_external_test_200.jsonl'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", fake_root)
    monkeypatch.setattr(module, "SCAN_DIRS", ["ai-service/scripts"])

    allowed, violations = module.audit_code_references()

    assert allowed == []
    assert len(violations) == 1
    assert violations[0]["path"] == "ai-service/scripts/train_with_external.py"
    assert violations[0]["purpose_hint"] == "train"
    assert "real_reviews_external_test_200.jsonl" in violations[0]["tokens"]
    assert "data/real_world/external_test" in violations[0]["tokens"]
