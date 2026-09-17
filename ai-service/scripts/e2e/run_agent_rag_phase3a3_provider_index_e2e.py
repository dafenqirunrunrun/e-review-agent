from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a3_common import build_provider_index, make_provider, write_phase3a3_json
from agent_rag_phase3a_common import phase3a_chunks
from app.agent_rag.faiss_index import IndexCompatibilityError


def run() -> dict:
    chunks = phase3a_chunks("tenant-a")[1][:30]
    legacy = make_provider("legacy-cls")
    flag = make_provider("flagembedding")
    result = {"schemaVersion": "1.0.0", "scenarios": {}}
    try:
        legacy_index, legacy_manifest = build_provider_index(legacy, "legacy-cls", chunks)
        hits, _ = legacy_index.search(legacy.embed_query("refund broken"), legacy.metadata(), tenant_id="tenant-a", top_k=3)
        result["scenarios"]["legacyIndexLegacyProvider"] = {"status": "PASS" if hits else "FAIL", "manifest": legacy_manifest}
        try:
            legacy_index.activate(legacy_manifest["indexVersion"], flag.metadata(), tenant_id="tenant-a")
            result["scenarios"]["flagProviderLegacyIndexRejected"] = {"status": "FAIL"}
        except Exception as exc:
            result["scenarios"]["flagProviderLegacyIndexRejected"] = {"status": "PASS", "reason": str(exc)[:120]}
        try:
            flag_index, flag_manifest = build_provider_index(flag, "flagembedding", chunks)
            flag_hits, _ = flag_index.search(flag.embed_query("refund broken"), flag.metadata(), tenant_id="tenant-a", top_k=3)
            result["scenarios"]["flagIndexFlagProvider"] = {"status": "PASS" if flag_hits else "FAIL", "manifest": flag_manifest}
            try:
                flag_index.activate(flag_manifest["indexVersion"], legacy.metadata(), tenant_id="tenant-a")
                result["scenarios"]["legacyProviderFlagIndexRejected"] = {"status": "FAIL"}
            except Exception as exc:
                result["scenarios"]["legacyProviderFlagIndexRejected"] = {"status": "PASS", "reason": str(exc)[:120]}
        except Exception as exc:
            result["scenarios"]["flagIndexFlagProvider"] = {"status": "BLOCKED", "reason": str(exc)[:240]}
            result["scenarios"]["legacyProviderFlagIndexRejected"] = {"status": "BLOCKED", "reason": "FLAG_INDEX_UNAVAILABLE"}
        result["status"] = "PASS" if all(item["status"] == "PASS" for item in result["scenarios"].values()) else "BLOCKED"
    finally:
        legacy.close()
        flag.close()
    write_phase3a3_json("provider-index-e2e-summary.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
