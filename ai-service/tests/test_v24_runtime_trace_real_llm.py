from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_real_llm_trace_artifact_requires_manifest_and_does_not_claim_quality() -> None:
    payload = json.loads((ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-real-llm.json").read_text(encoding="utf-8"))
    assert payload["realLlmRequired"] is True
    if not payload["qwen3Available"]:
        assert payload["status"] == "REAL_LLM_TRACE_BLOCKED_ASSET_MANIFEST_UNAVAILABLE"
    rendered = json.dumps(payload, ensure_ascii=False)
    assert "FULL_AGENT_QUALITY_QUALIFIED" not in rendered
    assert "PRODUCTION_LLM_CHAIN_QUALIFIED" not in rendered
