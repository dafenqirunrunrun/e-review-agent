from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v161_full_regression_wrapper_and_python_entrypoint_exist():
    wrapper = ROOT / "scripts/e-review-v161-full-regression.ps1"
    entrypoint = ROOT / "ai-service/scripts/v161_full_regression.py"
    assert wrapper.exists()
    assert entrypoint.exists()
    wrapper_text = wrapper.read_text(encoding="utf-8")
    entrypoint_text = entrypoint.read_text(encoding="utf-8")
    assert "v161_full_regression.py" in wrapper_text
    assert "--real-json" in wrapper_text
    assert "--vlm-candidates" in wrapper_text
    assert "--text-model-dirs" in wrapper_text
    assert "V161_REGRESSION_COMPLETE_WITH_BLOCKED_RELEASE_GATES" in entrypoint_text
    assert "V161_FINAL_GATE_BLOCKED" in entrypoint_text
    assert "unblock-prerequisites" in entrypoint_text
    assert "V161_UNBLOCK_PREREQUISITES_BLOCKED" in entrypoint_text
    assert "external-test-isolation" in entrypoint_text
    assert "EXTERNAL_TEST_ISOLATION_AUDIT_PASS" in entrypoint_text
    assert "local-vlm-smoke" in entrypoint_text
    assert "vlm-observability" in entrypoint_text
    assert "VLM_PROVIDER_SMOKE_BLOCKED" in entrypoint_text
    assert "VLM_OBSERVABILITY_BLOCKED" in entrypoint_text
