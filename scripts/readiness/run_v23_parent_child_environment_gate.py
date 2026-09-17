from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-environment-responsibility.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    envs = {item["environmentId"]: item for item in payload["environments"]}
    qualified = envs["B_QUALIFIED_REAL_MODEL"]
    default = envs["A_DEFAULT_DEVELOPMENT"]
    conflict = envs["C_CONFLICT_ENVIRONMENT"]
    checks = {
        "qualified pip check": qualified.get("pipCheckPass") is True,
        "torch import": qualified.get("torchImportPass") is True,
        "cuda available": qualified.get("cudaAvailable") is True,
        "faiss import": qualified.get("faissImportPass") is True,
        "default responsibility declared": default.get("qualificationStatus") == "DEFAULT_LOGIC_ONLY",
        "conflict excluded": conflict.get("qualificationStatus") == "DEPENDENCY_CONFLICT_ENVIRONMENT_NOT_QUALIFIED",
        "absolute paths redacted": payload.get("absolutePathsRedacted") is True,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("E_REVIEW_V23_PARENT_CHILD_QUALIFICATION_ENVIRONMENT_BLOCKED")
        for item in failed:
            print(f"FAILED: {item}")
        return 1
    print("E_REVIEW_V23_PARENT_CHILD_QUALIFICATION_ENVIRONMENT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
