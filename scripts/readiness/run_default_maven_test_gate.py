from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-rc" / "default-maven-test-gate.json"
EXTERNAL_STORAGE_TESTS = {
    "org.linlinjava.litemall.core.AliyunStorageTest",
    "org.linlinjava.litemall.core.QiniuStorageTest",
    "org.linlinjava.litemall.core.TencentStorageTest",
}


def main() -> int:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "mvn test -DskipTests=false"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    reports = parse_surefire_reports()
    skipped_external = sorted(
        name for name in EXTERNAL_STORAGE_TESTS
        if reports.get(name, {}).get("skipped", 0) > 0
    )
    external_enabled = is_external_storage_enabled()
    result = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "command": "mvn test -DskipTests=false",
        "returnCode": completed.returncode,
        "summary": summarize(reports),
        "externalStorageTests": {
            "enabled": external_enabled,
            "expected": sorted(EXTERNAL_STORAGE_TESTS),
            "skipped": skipped_external,
            "skippedWithoutCredentials": (not external_enabled) and set(skipped_external) == EXTERNAL_STORAGE_TESTS,
        },
        "boundaries": [
            "External object storage provider correctness is not claimed when credentials are absent.",
            "Production code, interfaces, and database schema are not modified by this gate.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if result["status"] != "PASS":
        print("E_REVIEW_DEFAULT_MAVEN_TEST_FAIL")
        print(json.dumps({"output": str(OUT), "returnCode": completed.returncode}, ensure_ascii=False))
        return 1

    print("E_REVIEW_DEFAULT_MAVEN_TEST_PASS")
    if result["externalStorageTests"]["skippedWithoutCredentials"]:
        print("E_REVIEW_EXTERNAL_STORAGE_TESTS_SKIPPED_WITHOUT_CREDENTIALS")
    elif external_enabled:
        print("E_REVIEW_EXTERNAL_STORAGE_TESTS_ENABLED")
    else:
        print("E_REVIEW_EXTERNAL_STORAGE_TEST_SKIP_STATUS_UNEXPECTED")
        return 2
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("MODEL_RERANKER_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    return 0


def is_external_storage_enabled() -> bool:
    env_enabled = os.environ.get("E_REVIEW_EXTERNAL_STORAGE_TESTS", "").strip().lower() == "true"
    property_enabled = any(
        flag.strip().lower() == "-de.review.external.storage.tests=true"
        for name in ("MAVEN_OPTS", "JAVA_TOOL_OPTIONS")
        for flag in os.environ.get(name, "").split()
    )
    return env_enabled or property_enabled


def parse_surefire_reports() -> dict[str, dict[str, int]]:
    reports: dict[str, dict[str, int]] = {}
    for path in ROOT.glob("**/target/surefire-reports/TEST-*.xml"):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        name = root.attrib.get("name", path.stem.replace("TEST-", ""))
        reports[name] = {
            "tests": int(root.attrib.get("tests", "0")),
            "failures": int(root.attrib.get("failures", "0")),
            "errors": int(root.attrib.get("errors", "0")),
            "skipped": int(root.attrib.get("skipped", "0")),
        }
    return reports


def summarize(reports: dict[str, dict[str, int]]) -> dict[str, int]:
    summary = {"classes": len(reports), "tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for report in reports.values():
        for key in ("tests", "failures", "errors", "skipped"):
            summary[key] += int(report.get(key, 0))
    return summary


if __name__ == "__main__":
    raise SystemExit(main())
