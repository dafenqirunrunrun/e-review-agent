from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    result = read_json(OUT / "v23-retrieval-representation-qualification.json")
    checks = {
        "datasetV2Present": result.get("datasetVersion") == "v23-retrieval-qualification-v2",
        "structuredQualified": result.get("structuredRetrievalDecision") == "STRUCTURED_RETRIEVAL_CONTENT_QUALIFIED",
        "sparseRuntimePass": (result.get("sparseRuntime") or {}).get("status") == "PASS",
        "runtimeIntegrationNotAllowedInPhase93": result.get("runtimeIntegrationAllowed") is False,
    }
    payload = {
        "schemaVersion": "agent-rag-v23-retrieval-representation-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "decision": "RETRIEVAL_REPRESENTATION_QUALIFIED" if all(checks.values()) else "RETRIEVAL_REPRESENTATION_QUALIFICATION_BLOCKED",
        "checks": checks,
        "blockedReason": "" if all(checks.values()) else "structured retrieval and/or real BGE-M3 sparse runtime did not qualify",
    }
    write_json(OUT / "v23-retrieval-representation-gate.json", payload)
    print("E_REVIEW_V23_RETRIEVAL_REPRESENTATION_QUALIFICATION_PASS" if payload["status"] == "PASS" else "E_REVIEW_V23_RETRIEVAL_REPRESENTATION_QUALIFICATION_BLOCKED")
    return 0 if payload["status"] == "PASS" else 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
