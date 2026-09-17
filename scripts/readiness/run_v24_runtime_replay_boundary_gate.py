from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-replay-boundary.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("replayEnabledByDefault") is False and p.get("replayHttpRouteExists") is False and p.get("realExternalToolCallsDuringReplay") == 0 and p.get("businessWritesDuringReplay") == 0
    print("E_REVIEW_V24_RUNTIME_REPLAY_BOUNDARY_PASS" if ok else "E_REVIEW_V24_RUNTIME_REPLAY_BOUNDARY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
