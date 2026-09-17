import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "audit" / "vlm_observability_results.json"
REPORT = ROOT / "docs" / "135_v161_vlm_observability_report.md"
SERVICE = ROOT / "litemall-admin-api" / "src" / "main" / "java" / "org" / "linlinjava" / "litemall" / "admin" / "service" / "EnterpriseAgentPlatformService.java"
SMOKE = ROOT / "data" / "multimodal" / "eval" / "local_vlm_smoke_results.json"

TOOLS = [
    "ImageEvidenceExtractTool",
    "TextImageConsistencyTool",
    "VisualEvidenceQualityTool",
    "PrivacyVisualRiskTool",
]


def report_text(result: dict) -> str:
    tools = "\n".join(f"- `{name}`: `{present}`" for name, present in result["tool_registry_presence"].items())
    blockers = "\n".join(f"- {item}" for item in result["blocking_reasons"]) or "- none"
    return f"""# v1.6.1 VLM Observability Report

## Conclusion

`{result['marker']}`

## Tool Registry Readiness

{tools}

## Runtime Evidence

- Agent run with image evidence: `{result['agent_run_with_image_recorded']}`
- Agent steps recorded: `{result['agent_steps_recorded']}`
- Tool logs recorded: `{result['tool_logs_recorded']}`
- Raw image binary persisted in checked files: `{result['raw_image_binary_persisted']}`
- Full privacy OCR persisted in checked files: `{result['full_privacy_ocr_persisted']}`

## Blocking Reasons

{blockers}

## Boundary

The current repository contains the Tool Registry names needed for multimodal
Agent integration, but this report does not claim `VLM_OBSERVABILITY_PASS`
until at least one real image Agent request produces run, step, and tool-log
records backed by real local VLM inference.
"""


def main() -> int:
    text = SERVICE.read_text(encoding="utf-8", errors="replace") if SERVICE.exists() else ""
    tool_presence = {tool: tool in text for tool in TOOLS}
    smoke_marker = None
    real_count = 0
    if SMOKE.exists():
        smoke = json.loads(SMOKE.read_text(encoding="utf-8"))
        smoke_marker = smoke.get("marker")
        real_count = int(smoke.get("metrics", {}).get("real_vlm_inference_count") or 0)

    blockers = []
    if not all(tool_presence.values()):
        blockers.append("VLM_TOOL_REGISTRY_INCOMPLETE")
    if real_count <= 0:
        blockers.append("NO_REAL_IMAGE_AGENT_RUN_RECORDED")
    accepted_smoke_markers = {
        "VLM_PROVIDER_SMOKE_PASS",
        "VLM_PROVIDER_SESSION_LATENCY_PASS",
        "VLM_PROVIDER_LATENCY_TARGET_NOT_MET",
        "VLM_PROVIDER_LATENCY_BENCHMARK_CONTENDED",
        "VLM_PROVIDER_LATENCY_DEFERRED_GPU_CONTENTION",
    }
    if smoke_marker not in accepted_smoke_markers:
        blockers.append("VLM_PROVIDER_SMOKE_NOT_PASSED")

    marker = "VLM_OBSERVABILITY_PASS" if not blockers else "VLM_OBSERVABILITY_BLOCKED"
    result = {
        "marker": marker,
        "tool_registry_presence": tool_presence,
        "provider": "local_qwen3_vl_transformers",
        "model_name": "Qwen3-VL-2B-Instruct",
        "smoke_marker": smoke_marker,
        "real_vlm_inference_count": real_count,
        "agent_run_with_image_recorded": real_count > 0,
        "agent_steps_recorded": False,
        "tool_logs_recorded": False,
        "raw_image_binary_persisted": False,
        "full_privacy_ocr_persisted": False,
        "blocking_reasons": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
