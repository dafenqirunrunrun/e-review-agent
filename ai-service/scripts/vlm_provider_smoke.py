import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = ROOT / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.main import app

OUT = ROOT / "data" / "multimodal" / "eval" / "vlm_provider_smoke_results.json"
REPORT = ROOT / "docs" / "127_v161_vlm_provider_smoke_report.md"


def run_smoke() -> dict:
    client = TestClient(app)
    status = client.get("/api/v1/vlm/status").json()
    smoke = client.post("/api/v1/vlm/smoke-test").json()

    model_available = status.get("model_available") is True
    schema_valid = smoke.get("schema_valid") is True
    provider_marker = smoke.get("marker", "MISSING")

    if model_available and schema_valid and provider_marker == "MULTIMODAL_VLM_PILOT_READY":
        marker = "VLM_PROVIDER_SMOKE_READY_FOR_REAL_IMAGE_TEST"
    else:
        marker = "VLM_PROVIDER_SMOKE_BLOCKED"

    blockers = []
    if not model_available:
        blockers.append(status.get("blocked_reason") or "VLM_MODEL_NOT_AVAILABLE")
    if not schema_valid:
        blockers.append("VLM_SCHEMA_VALIDATION_FAILED")
    if provider_marker == "MULTIMODAL_VLM_EVAL_BLOCKED":
        blockers.append("provider smoke endpoint returned MULTIMODAL_VLM_EVAL_BLOCKED")

    return {
        "marker": marker,
        "provider_marker": provider_marker,
        "model_available": model_available,
        "schema_valid": schema_valid,
        "provider": status.get("provider"),
        "model_name": status.get("model_name"),
        "model_dir_kind": "repo_external_configured_path",
        "device": status.get("device"),
        "dtype": status.get("dtype"),
        "load_in_4bit": status.get("load_in_4bit"),
        "memory_strategy": status.get("memory_strategy"),
        "blocked_reason": status.get("blocked_reason"),
        "blocking_reasons": blockers,
        "status_endpoint": "/api/v1/vlm/status",
        "smoke_endpoint": "/api/v1/vlm/smoke-test",
        "message": smoke.get("message"),
    }


def report_text(result: dict) -> str:
    blockers = "\n".join(f"- {item}" for item in result["blocking_reasons"]) or "- none"
    return f"""# v1.6.1 VLM Provider Smoke Report

## Conclusion

`{result['marker']}`

- Provider marker: `{result['provider_marker']}`
- Model available: `{result['model_available']}`
- Schema valid: `{result['schema_valid']}`
- Provider: `{result['provider']}`
- Model name: `{result['model_name']}`
- Model directory kind: `{result['model_dir_kind']}`
- Device: `{result['device']}`
- dtype: `{result['dtype']}`
- 4-bit: `{result['load_in_4bit']}`
- Memory strategy: `{result['memory_strategy']}`

## Endpoints

- Status: `{result['status_endpoint']}`
- Smoke test: `{result['smoke_endpoint']}`

## Blocking Reasons

{blockers}

## Evidence Boundary

This smoke check validates the VLM provider wiring, status endpoint, smoke-test
endpoint, and schema path. It does not claim real VLM inference success while
the local VLM weights and real image smoke samples are unavailable.
"""


def main() -> int:
    result = run_smoke()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
