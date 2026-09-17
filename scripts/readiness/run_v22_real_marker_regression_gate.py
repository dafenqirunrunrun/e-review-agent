from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "real-model-chain"
MARKERS = {
    "real_dense": "ai-service/tests",
    "real_reranker": "ai-service/tests",
    "real_llm": "ai-service/tests/test_v200_agent_rag_phase4_local_llm.py",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-manifest", default=os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", ""))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", default=str(OUT / "v22-real-marker-regression-gate.json"))
    args = parser.parse_args()

    env = os.environ.copy()
    if args.asset_manifest:
        env["AGENT_RAG_V22_ASSET_MANIFEST"] = args.asset_manifest
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("RAG_RERANKER_DEVICE", "cuda")
    env.setdefault("RAG_RERANKER_USE_FP16", "true")

    marker_results: dict[str, Any] = {}
    for marker, target in MARKERS.items():
        junit_path = OUT / f"pytest-{marker}.xml"
        command = [
            args.python,
            "-m",
            "pytest",
            "-ra",
            "-m",
            marker,
            target,
            f"--junitxml={junit_path}",
        ]
        completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        parsed = parse_junit(junit_path)
        marker_results[marker] = {
            **parsed,
            "exitCode": completed.returncode,
            "command": sanitize(" ".join(command)),
            "stdoutTail": [sanitize(line) for line in tail(completed.stdout)],
            "stderrTail": [sanitize(line) for line in tail(completed.stderr)],
            "junitArtifact": junit_path.relative_to(ROOT).as_posix(),
            "pass": completed.returncode == 0 and parsed["selected"] > 0 and parsed["passed"] > 0,
        }

    checks = {
        "realDenseSelected": marker_results["real_dense"]["selected"] > 0,
        "realDensePassed": marker_results["real_dense"]["passed"] > 0,
        "realRerankerSelected": marker_results["real_reranker"]["selected"] > 0,
        "realRerankerPassed": marker_results["real_reranker"]["passed"] > 0,
        "realLlmSelected": marker_results["real_llm"]["selected"] > 0,
        "realLlmPassed": marker_results["real_llm"]["passed"] > 0,
    }
    status = "PASS" if all(checks.values()) and all(item["exitCode"] == 0 for item in marker_results.values()) else "FAIL"
    payload = {
        "schemaVersion": "agent-rag-v22-real-marker-regression-gate-v1",
        "createdAtUtc": now(),
        "status": status,
        "checks": checks,
        "markers": marker_results,
        "tokens": ["AGENT_RAG_V22_REAL_MARKER_REGRESSION_PASS"] if status == "PASS" else [],
        "boundaries": [] if status == "PASS" else ["REAL_MODEL_MARKER_REGRESSION_BLOCKED"],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if status == "PASS":
        print("AGENT_RAG_V22_REAL_MARKER_REGRESSION_PASS")
        return 0
    print("AGENT_RAG_V22_REAL_MARKER_REGRESSION_FAIL")
    return 1


def parse_junit(path: Path) -> dict[str, int]:
    if not path.exists():
        return {"selected": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    selected = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
    return {
        "selected": selected,
        "passed": max(0, selected - failures - errors - skipped),
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
    }


def tail(value: str, max_lines: int = 20) -> list[str]:
    return value.splitlines()[-max_lines:]


def sanitize(value: str) -> str:
    return value.replace(str(ROOT), "<repo>").replace(str(Path(sys.executable)), "<python>")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
