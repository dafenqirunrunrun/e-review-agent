from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, sanitize_request_id


ROOT = Path(__file__).resolve().parents[2]


def load_module(path: Path, name: str):
    sys.path.insert(0, str(ROOT / "scripts" / "ci"))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


security_gate = load_module(ROOT / "scripts" / "ci" / "public_container_security_gate.py", "public_container_security_gate_test")
phase3_gate = load_module(ROOT / "scripts" / "readiness" / "run_public_ops_phase3_gate.py", "public_ops_phase3_gate_test")


def test_request_id_keeps_valid_value():
    assert sanitize_request_id("req-123.A_B:9") == "req-123.A_B:9"


@pytest.mark.parametrize("value", ["bad\r\nid", "x" * 129, "bad request", ""])
def test_request_id_replaces_invalid_values(value):
    sanitized = sanitize_request_id(value)
    assert sanitized != value
    assert "\r" not in sanitized
    assert "\n" not in sanitized
    assert len(sanitized) <= 128


def test_request_id_header_crlf_is_replaced():
    client = TestClient(app)
    response = client.get("/health/ready", headers={"X-Request-ID": "bad%0Aid"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] != "bad%0Aid"


def finding(severity="HIGH", version="1.0"):
    return {
        "target": "target-a",
        "pkgName": "pkg-a",
        "vulnerabilityId": "CVE-2099-0001",
        "severity": severity,
        "installedVersion": version,
        "fixedVersion": "2.0",
    }


def exception(**overrides):
    item = {
        **finding(),
        "reason": "legacy public demo dependency",
        "remediation": "upgrade in a hardening PR",
        "owner": "repository-maintainer",
        "trackingIssue": "https://github.com/dafenqirunrunrun/e-review-agent/issues/29",
        "createdAt": "2026-07-19",
        "expires": "2026-10-17",
        "disposition": "accepted-temporarily",
        "reachability": "unknown",
    }
    item.update(overrides)
    return item


def validate(exceptions, findings=None):
    findings = findings or [finding()]
    keys = {security_gate._finding_key(row) for row in findings}
    return security_gate._validate_exception_schema(exceptions, keys)


def test_valid_exception_matches():
    result = validate([exception()])
    assert not result["invalid"]
    assert not result["orphan"]


def test_expired_exception_fails(monkeypatch):
    monkeypatch.setenv("PUBLIC_SECURITY_GATE_TODAY", "2026-10-18")
    result = validate([exception()])
    assert result["expired"]
    assert result["invalid"]


def test_installed_version_mismatch_fails_as_orphan():
    result = validate([exception(installedVersion="9.9")])
    assert result["orphan"]
    assert result["invalid"]


def test_severity_mismatch_fails_as_orphan():
    result = validate([exception(severity="CRITICAL", criticalRiskStatement="critical risk remains")])
    assert result["orphan"]
    assert result["invalid"]


def test_duplicate_exception_fails():
    result = validate([exception(), exception()])
    assert result["duplicate"]
    assert result["invalid"]


def test_orphan_exception_fails():
    result = validate([exception(pkgName="pkg-b")])
    assert result["orphan"]
    assert result["invalid"]


def test_missing_field_fails():
    item = exception()
    del item["owner"]
    result = validate([item])
    assert result["invalid"]


def test_critical_exception_requires_risk_statement():
    critical = exception(severity="CRITICAL")
    result = validate([critical], [finding(severity="CRITICAL")])
    assert result["invalid"]


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_evidence(status="PASS", **extra):
    payload = {
        "schemaVersion": "test",
        "sourceCommit": "abc",
        "workflowRunId": "1",
        "generatedAt": "2026-07-19T00:00:00Z",
        "status": status,
        "checks": {},
        "boundaries": ["PRODUCTION_READY_NOT_CLAIMED"],
    }
    payload.update(extra)
    return payload


def test_phase3_gate_does_not_pass_empty_file(tmp_path, monkeypatch):
    monkeypatch.setattr(phase3_gate, "RUNTIME_EVIDENCE", tmp_path)
    monkeypatch.setattr(phase3_gate, "EVIDENCE", tmp_path)
    (tmp_path / "observability-smoke-summary.json").write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError):
        phase3_gate._validate_observability()


def test_phase3_gate_rejects_failed_status(tmp_path, monkeypatch):
    monkeypatch.setattr(phase3_gate, "RUNTIME_EVIDENCE", tmp_path)
    write_json(tmp_path / "observability-smoke-summary.json", base_evidence(status="FAIL", requestIdPropagation=True, metricsVerified=True))
    with pytest.raises(RuntimeError):
        phase3_gate._validate_observability()


def test_phase3_gate_rejects_sbom_missing_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(phase3_gate, "EVIDENCE", tmp_path)
    sbom_dir = tmp_path / "sbom"
    for name in ["backend", "ai-service", "admin", "customer"]:
        write_json(sbom_dir / f"{name}.spdx.json", {"name": name})
    manifest = base_evidence(tool="trivy", toolVersion="trivy 1.0", images={
        name: {"image": name, "sbomPath": str((sbom_dir / f"{name}.spdx.json").relative_to(ROOT)) if False else str(sbom_dir / f"{name}.spdx.json"), "sbomSha256": "abc"}
        for name in ["backend", "ai-service", "admin", "customer"]
    })
    write_json(sbom_dir / "manifest.json", manifest)
    with pytest.raises(RuntimeError):
        phase3_gate._validate_sbom()
