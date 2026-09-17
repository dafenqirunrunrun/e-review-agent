from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE = ROOT / "ai-service"
if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))

from app.agent_rag.target_mode import DEFAULT_RETRIEVAL_MODE, load_agent_rag_target_config

OUT = ROOT / "artifacts" / "agent-rag" / "v2.1-reproducibility" / "provider-selection-contract-gate-result.json"


def main() -> int:
    cfg = load_agent_rag_target_config()
    checks = {
        "enterpriseTargetMode": cfg.target_mode == "enterprise-maturity-local-single-node",
        "providerSelectionRecorded": bool(cfg.bge_m3_provider_impl),
        "retrievalDefaultStable": cfg.default_retrieval_mode == DEFAULT_RETRIEVAL_MODE,
        "fallbackPolicyExplicit": isinstance(cfg.rule_fallback_enabled, bool),
        "realDenseFlagExplicit": isinstance(cfg.real_dense_required, bool),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schemaVersion": "1.0.0",
        "status": status,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "targetMode": cfg.target_mode,
        "selectedProviderImpl": cfg.bge_m3_provider_impl,
        "denseProvider": cfg.dense_provider,
        "defaultRetrievalMode": cfg.default_retrieval_mode,
        "rerankerType": cfg.reranker_type,
        "llmProvider": cfg.llm_provider,
        "ruleFallbackEnabled": cfg.rule_fallback_enabled,
        "realDenseRequired": cfg.real_dense_required,
        "assetRuntimeLoaded": False,
        "checks": checks,
        "environmentContract": {
            "AGENT_RAG_TARGET_MODE": os.environ.get("AGENT_RAG_TARGET_MODE"),
            "RAG_BGE_M3_PROVIDER_IMPL": os.environ.get("RAG_BGE_M3_PROVIDER_IMPL"),
            "RAG_DEFAULT_RETRIEVAL_MODE": os.environ.get("RAG_DEFAULT_RETRIEVAL_MODE"),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if status == "PASS":
        print("AGENT_RAG_PROVIDER_SELECTION_CONTRACT_PASS")
        print("AGENT_RAG_RETRIEVAL_DEFAULT_PASS")
        print("AGENT_RAG_ENTERPRISE_TARGET_MODE_PASS")
        return 0
    print("AGENT_RAG_PROVIDER_SELECTION_CONTRACT_FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
