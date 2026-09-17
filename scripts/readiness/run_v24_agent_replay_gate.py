from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts" / "agent-productionization"


def main() -> int:
    structural = json.loads((BASE / "v24-agent-replay-structural-result.json").read_text(encoding="utf-8"))
    deterministic = json.loads((BASE / "v24-agent-replay-deterministic-result.json").read_text(encoding="utf-8"))
    side_effect = json.loads((BASE / "v24-agent-replay-side-effect-result.json").read_text(encoding="utf-8"))
    ok = (
        structural.get("structuralReplayPass") is True
        and structural.get("outcomeHashMatches") == structural.get("traceCount")
        and deterministic.get("deterministicReplayPass") is True
        and deterministic.get("providerStubReplayPass") is True
        and side_effect.get("sideEffectGuardPass") is True
    )
    print("E_REVIEW_V24_AGENT_REPLAY_FOUNDATION_PASS" if ok else "E_REVIEW_V24_AGENT_REPLAY_FOUNDATION_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
