import json
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dependencies.audit_phase3a3_provider_dependencies import DistributionInfo, audit_environment, marker_applies
from dependencies.verify_phase3a3_wheelhouse import verify_wheelhouse


def fake_provider(packages):
    def _provider(name):
        return packages.get(name.lower())

    return _provider


def test_phase3a31_dependency_audit_reports_missing_packages():
    payload = audit_environment(distribution_provider=fake_provider({}))
    assert payload["status"] == "BLOCKED"
    assert {item["name"] for item in payload["missing"]} == {"FlagEmbedding", "sentence-transformers"}


def test_phase3a31_dependency_audit_reports_version_mismatch():
    packages = {"flagembedding": DistributionInfo("FlagEmbedding", "1.3.4")}
    payload = audit_environment(targets=("FlagEmbedding==1.3.5",), distribution_provider=fake_provider(packages))
    assert payload["status"] == "BLOCKED"
    assert payload["versionMismatches"][0]["installed"] == "1.3.4"


def test_phase3a31_dependency_audit_accepts_higher_version_for_range_dependency():
    packages = {
        "flagembedding": DistributionInfo("FlagEmbedding", "1.3.5", ("packaging>=23",)),
        "packaging": DistributionInfo("packaging", "24.2"),
    }
    payload = audit_environment(targets=("FlagEmbedding==1.3.5",), distribution_provider=fake_provider(packages))
    assert payload["status"] == "PASS"
    assert any(item["name"] == "packaging" for item in payload["satisfied"])


def test_phase3a31_dependency_audit_ignores_extra_marker():
    requirement = Requirement("datasets; extra == 'train'")
    assert marker_applies(requirement) is False
    packages = {"flagembedding": DistributionInfo("FlagEmbedding", "1.3.5", ("datasets; extra == 'train'",))}
    payload = audit_environment(targets=("FlagEmbedding==1.3.5",), distribution_provider=fake_provider(packages))
    assert payload["status"] == "PASS"
    assert payload["ignoredMarkers"]


def test_phase3a31_dependency_audit_json_output(tmp_path):
    output = tmp_path / "audit.json"
    completed = subprocess.run(
        [sys.executable, "ai-service/scripts/dependencies/audit_phase3a3_provider_dependencies.py", "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode in {0, 2}
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["networkUsed"] is False
    assert payload["environmentModified"] is False


def test_phase3a31_wheelhouse_reports_missing_required(tmp_path):
    payload = verify_wheelhouse(tmp_path / "wheelhouse", tmp_path / "sources")
    assert payload["status"] == "BLOCKED"
    assert payload["missingRequired"]


def test_phase3a31_wheelhouse_rejects_torch_wheels(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / "torch-2.5.1-cp310-cp310-win_amd64.whl").write_bytes(b"not a real wheel")
    payload = verify_wheelhouse(wheelhouse)
    assert payload["status"] == "BLOCKED"
    assert payload["torchWheelPresent"] is True
    assert payload["forbiddenFiles"]
