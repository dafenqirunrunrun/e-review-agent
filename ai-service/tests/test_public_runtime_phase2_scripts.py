from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "ci"


def load_script(name: str, relative_path: str | None = None):
    sys.path.insert(0, str(SCRIPTS))
    path = ROOT / relative_path if relative_path else SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_wait_until_success_and_timeout():
    common = load_script("public_runtime_common")
    assert common.wait_until("instant", lambda: "ok", timeout_seconds=1, interval_seconds=0.01) == "ok"
    with pytest.raises(common.PublicRuntimeError):
        common.wait_until("never", lambda: (_ for _ in ()).throw(RuntimeError("not yet")), timeout_seconds=0.03, interval_seconds=0.01)


def test_litemall_response_assertion():
    common = load_script("public_runtime_common")
    assert common.assert_litemall_ok({"errno": 0, "data": {"id": 1}}, "ok") == {"id": 1}
    with pytest.raises(common.PublicRuntimeError):
        common.assert_litemall_ok({"errno": 502, "errmsg": "failed"}, "bad")


def test_phase2_gate_blocks_without_evidence(tmp_path, monkeypatch):
    gate = load_script("run_public_runtime_phase2_gate", "scripts/readiness/run_public_runtime_phase2_gate.py")
    monkeypatch.setattr(gate, "EVIDENCE_DIR", tmp_path)
    assert gate.main() == 1


def test_phase2_gate_generates_json_only_with_evidence(tmp_path, monkeypatch):
    gate = load_script("run_public_runtime_phase2_gate", "scripts/readiness/run_public_runtime_phase2_gate.py")
    monkeypatch.setattr(gate, "EVIDENCE_DIR", tmp_path)
    for name in gate.REQUIRED:
        (tmp_path / name).write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    assert gate.main() == 0
    result = json.loads((tmp_path / "gate-result.json").read_text(encoding="utf-8"))
    assert result["runtimeMode"] == "public-rule"
    assert result["productionReady"] is False
