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

from agent_rag_phase3a3_common import PROVIDER_IMPLS, make_provider, vector_sanity, write_phase3a3_json


def run() -> dict:
    rows = json.loads((AI_ROOT / "tests" / "fixtures" / "agent_rag" / "phase3a2_sanity" / "sanity_cases.json").read_text(encoding="utf-8"))
    providers = {}
    for impl in PROVIDER_IMPLS:
        provider = make_provider(impl)
        try:
            providers[impl] = {"status": "PASS", **vector_sanity(provider, rows)}
        except Exception as exc:
            providers[impl] = {"status": "BLOCKED", "reason": str(exc)[:240], "caseCount": len(rows)}
        finally:
            provider.close()
    output = {"schemaVersion": "1.0.0", "providers": providers}
    write_phase3a3_json("provider-sanity-summary.json", output)
    return output


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
