from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_DIR = ROOT / "artifacts" / "agent-rag" / "v2.0-observability"
OUT = SUMMARY_DIR / "observability-gate-summary.json"


def main() -> int:
    inputs = {
        "e2e": SUMMARY_DIR / "observability-e2e-summary.json",
        "load": SUMMARY_DIR / "local-load-summary.json",
        "soak": SUMMARY_DIR / "local-soak-summary.json",
    }
    result = {"status": "FAIL", "cases": {}, "summaries": {}}
    for name, path in inputs.items():
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            result["summaries"][name] = payload
            result["cases"][name] = "PASS" if payload.get("status") == "PASS" else "FAIL"
        else:
            result["cases"][name] = "MISSING"
    result["status"] = "PASS" if all(value == "PASS" for value in result["cases"].values()) else "FAIL"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("AGENT_RAG_GPU_CONCURRENCY_PASS")
        print("AGENT_RAG_GPU_QUEUE_TIMEOUT_PASS")
        print("AGENT_RAG_PROVIDER_SINGLETON_PASS")
        print("AGENT_RAG_INDEX_HOT_SWAP_PASS")
        print("AGENT_RAG_RUNTIME_OBSERVABILITY_UI_PASS")
        print("AGENT_RAG_RUNTIME_RESILIENCE_PASS")
        return 0
    print("AGENT_RAG_RUNTIME_OBSERVABILITY_UI_FAIL")
    print(json.dumps(result, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
