from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    dataset_gate = read_json(OUT / "v23-retrieval-dataset-gate.json")
    baseline_gate = read_json(OUT / "v23-retrieval-baseline-gate.json")
    miss_gate = read_json(OUT / "v23-retrieval-miss-analysis-gate.json")
    sensitive = sensitive_scan()
    diff_check = run_diff_check()
    checks = {
        "datasetGatePass": dataset_gate.get("status") == "PASS",
        "baselineComplete": baseline_gate.get("status") == "PASS",
        "missAnalysisComplete": miss_gate.get("status") == "PASS",
        "noSensitiveDataLeak": sensitive["status"] == "PASS",
        "diffCheckPass": diff_check["status"] == "PASS",
        "noRetrievalQualityClaim": forbidden_claims_absent(),
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    payload = {
        "schemaVersion": "agent-rag-v23-phase-90-91-gate-v1",
        "status": status,
        "checks": checks,
        "sensitiveScan": sensitive,
        "diffCheck": diff_check,
        "tokens": [
            "E_REVIEW_V23_PHASE_90_PASS",
            "E_REVIEW_V23_PHASE_91_PASS",
            "E_REVIEW_V23_RETRIEVAL_OPTIMIZATION_FOUNDATION_PASS",
        ]
        if status == "PASS"
        else ["E_REVIEW_V23_RETRIEVAL_OPTIMIZATION_FOUNDATION_BLOCKED"],
        "qualityClaim": "FOUNDATION_PASS_NOT_RETRIEVAL_QUALITY_PASS",
    }
    write_json(OUT / "v23-phase-90-91-gate.json", payload)
    for token in payload["tokens"]:
        print(token)
    return 0 if status == "PASS" else 1


def sensitive_scan() -> dict[str, Any]:
    scanned = []
    findings = []
    roots = [OUT, ROOT / "docs" / "retrieval-optimization", ROOT / "ai-service" / "scripts" / "qualification", ROOT / "scripts" / "readiness"]
    patterns = [
        "D:" + "\\",
        "C:" + "\\Users" + "\\",
        "BEGIN" + " PRIVATE KEY",
        "password" + "=",
        "query" + '":"',
        "chunk" + "Text",
        "modelPath" + '":"D:',
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".py"}:
                continue
            relative = str(path.relative_to(ROOT))
            if relative == "artifacts\\retrieval-optimization\\v23-phase-90-91-gate.json":
                continue
            if relative == "scripts\\readiness\\run_v23_phase_90_91_gate.py":
                continue
            if path.suffix.lower() == ".py" and not path.name.startswith(("v23_", "run_v23_", "build_v23_")):
                continue
            if path.suffix.lower() == ".json" and not path.name.startswith("v23-"):
                continue
            if path.suffix.lower() == ".md" and not path.name.startswith("V23_"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            scanned.append(relative)
            for pattern in patterns:
                if pattern.lower() in text.lower():
                    findings.append({"file": str(path.relative_to(ROOT)), "pattern": pattern})
    allowed = [
        item
        for item in findings
        if item["file"].endswith(".py")
        and item["pattern"] in {"D:\\\\", "query\":\"", "modelPath\":\"D:"}
    ]
    blocking = [item for item in findings if item not in allowed]
    return {"status": "PASS" if not blocking else "FAIL", "scannedFiles": len(scanned), "blockingFindings": blocking[:20], "allowedCodeFindings": allowed[:20]}


def run_diff_check() -> dict[str, Any]:
    completed = subprocess.run(["git", "diff", "--check"], cwd=ROOT, text=True, capture_output=True, check=False)
    return {"status": "PASS" if completed.returncode == 0 else "FAIL", "returnCode": completed.returncode, "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()}


def forbidden_claims_absent() -> bool:
    forbidden = {"RETRIEVAL_QUALITY_VERIFIED", "PRODUCTION_RETRIEVAL_PASS"}
    files = list(OUT.glob("v23-*.json")) + list((ROOT / "docs" / "retrieval-optimization").glob("V23_*.md"))
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            if token in text and "forbidden" not in text.lower():
                return False
    return True


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
