from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_common import write_hierarchy_artifacts  # noqa: E402


def main() -> int:
    audit, manifest = write_hierarchy_artifacts()
    print(f"parentUnitCount={audit['parentUnitCount']}")
    print(f"childChunkCount={audit['childChunkCount']}")
    print(f"parentIndexFingerprint={manifest['parentIndexFingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
