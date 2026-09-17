from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "qualification" / "v23-parent-child-retrieval-candidate.yml"


EXPECTED = {
    "parentRepresentation": "P2",
    "strategy": "H2",
    "parentTopN": "20",
    "parentPriorEnabled": "true",
    "parentPriorConstant": "60",
    "postFusionCandidateK": "30",
    "maximumFinalK": "5",
    "allowBackfill": "false",
    "sparseEnabled": "false",
    "modelRerankerEnabled": "false",
    "evaluationRead": "false",
    "challengeRead": "false",
}


def parse() -> dict[str, str]:
    values = {}
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.strip().startswith("#"):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    values = parse()
    drift = [key for key, value in EXPECTED.items() if values.get(key) != value]
    if drift:
        print("PARENT_CHILD_CONFIGURATION_DRIFT_DETECTED")
        for key in drift:
            print(f"FAILED: {key}")
        return 1
    print("E_REVIEW_V23_PARENT_CHILD_CONFIGURATION_LOCK_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
