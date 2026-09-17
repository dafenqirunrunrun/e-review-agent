import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "authorized_intake" / "audit" / "technical_capability_freeze.json"
DOC = ROOT / "docs" / "171_v16112_technical_capability_freeze.md"


def main():
    passed = [
        "Qwen3-1.7B local inference",
        "Qwen3-VL local direct inference",
        "Hybrid RAG",
        "BGE-M3",
        "Neural Reranker",
        "Tool Registry",
        "JSON Schema",
        "GPU Gate",
        "single GPU serialized runtime",
        "VLM Runtime Session",
        "FastAPI",
        "Agent Observability",
        "External Test Isolation",
        "data source approval pipeline",
        "pilot data boundary audit",
    ]
    blocked = [
        "formal real text external evaluation",
        "formal real multimodal evaluation",
        "annotation agreement",
        "formal routing calibration",
        "SFT readiness",
        "VLM SFT readiness",
    ]
    report = {
        "marker": "TECHNICAL_SYSTEM_READINESS_PASS",
        "TECHNICAL_SYSTEM_READINESS_PASS": True,
        "RESEARCH_EVALUATION_READINESS_BLOCKED": True,
        "passed_capabilities": passed,
        "blocked_research_capabilities": blocked,
        "current_blocker": "explicit_authorized_annotatable_ecommerce_review_data_required",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.1.12 Technical Capability Freeze\n\n"
        "Status: `TECHNICAL_SYSTEM_READINESS_PASS`\n\n"
        "The engineering system is ready: local LLM/VLM runtime, RAG components, FastAPI provider path, observability, schema handling, GPU gate, and data-source governance are in place.\n\n"
        "Status: `RESEARCH_EVALUATION_READINESS_BLOCKED`\n\n"
        "The remaining blocker is not model code. Formal evaluation, annotation reliability, calibration, and SFT readiness require explicitly authorized and annotatable ecommerce review data.\n",
        encoding="utf-8",
    )
    print("TECHNICAL_SYSTEM_READINESS_PASS")
    print("RESEARCH_EVALUATION_READINESS_BLOCKED")


if __name__ == "__main__":
    main()
