from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase4"


def contains(path: str, needles: list[str]) -> dict[str, bool]:
    text = (ROOT / path).read_text(encoding="utf-8")
    return {needle: needle in text for needle in needles}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-ra",
            "ai-service/tests/test_v200_agent_rag_phase4_local_llm.py",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    checks = {
        "targetedTests": tests.returncode == 0 and "4 passed" in tests.stdout,
        "decider": all(
            contains(
                "ai-service/app/agent_rag/llm_decider.py",
                [
                    "AGENT_RAG_LLM_NO_GROUNDED_CONTEXT",
                    "local_qwen3_transformers",
                    "LocalQwenTransformersProvider",
                    "Decision(",
                ],
            ).values()
        ),
        "runtimeWiring": all(
            contains(
                "ai-service/app/agent_rag/runtime.py",
                [
                    "analyze_with_grounded_local_llm",
                    "requestedLlmProvider",
                    "effectiveLlmProvider",
                    "llmFallbackReason",
                ],
            ).values()
        ),
        "internalHealth": all(
            contains(
                "ai-service/app/api/agent_rag_internal.py",
                [
                    "agent_rag_llm_status",
                    "\"llm\"",
                ],
            ).values()
        ),
        "noFakeRealPass": all(
            contains(
                "ai-service/tests/test_v200_agent_rag_phase4_local_llm.py",
                [
                    "FakeLocalQwenProvider",
                    "default_deterministic_path_is_unchanged",
                    "no_grounded_context_falls_back_without_calling_llm",
                ],
            ).values()
        ),
    }
    result = {
        "schemaVersion": "agent-rag-phase4-local-llm-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "testReturnCode": tests.returncode,
        "boundaries": [
            "LOCAL_LLM_OPTIONAL",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "NO_FAKE_REAL_LLM_PASS",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    (OUT / "phase4-local-llm-gate-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result["status"] != "PASS":
        print("AGENT_RAG_PHASE4_LOCAL_LLM_GATE_FAIL")
        print(tests.stdout[-4000:])
        print(tests.stderr[-4000:])
        raise SystemExit(2)
    print("AGENT_RAG_LOCAL_LLM_OPTIONAL_PROVIDER_PASS")
    print("AGENT_RAG_LOCAL_LLM_GROUNDED_CONTEXT_PASS")
    print("AGENT_RAG_LOCAL_LLM_FALLBACK_BOUNDARY_PASS")
    print("AGENT_RAG_PHASE4_LOCAL_LLM_GATE_PASS")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("NO_FAKE_REAL_LLM_PASS")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
