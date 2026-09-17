from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "artifacts" / "agent-rag" / "v2.0-admin-operations" / "admin-operations-summary.json"


PASS_TOKENS = [
    "AGENT_RAG_ADMIN_ROUTE_PASS",
    "AGENT_RAG_ADMIN_OVERVIEW_PASS",
    "AGENT_RAG_ADMIN_RUN_LIST_PASS",
    "AGENT_RAG_ADMIN_RUN_DETAIL_PASS",
    "AGENT_RAG_ADMIN_EVIDENCE_TIMELINE_PASS",
    "AGENT_RAG_ADMIN_OVERRIDE_PASS",
    "AGENT_RAG_ADMIN_REPLAY_PASS",
    "AGENT_RAG_ADMIN_RUNTIME_STATUS_PASS",
    "AGENT_RAG_ADMIN_PERMISSION_PASS",
    "AGENT_RAG_ADMIN_BUILD_PASS",
    "AGENT_RAG_ADMIN_RUNTIME_E2E_PASS",
    "AGENT_RAG_ADMIN_OPERATIONS_PASS",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default=str(SUMMARY))
    parser.add_argument("--frontend-build", default="")
    parser.add_argument("--frontend-unit", default="")
    parser.add_argument("--java-targeted", default="")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    failures: list[str] = []
    if not summary_path.exists():
        failures.append("summary.missing")
        summary = {}
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    cases = summary.get("cases") or {}
    frontend_build = args.frontend_build or summary.get("frontendBuild")
    frontend_unit = args.frontend_unit or summary.get("frontendUnit")
    java_targeted = args.java_targeted or summary.get("javaTargeted")

    require(failures, summary.get("status") == "PASS", "summary.status")
    require(failures, frontend_build == "PASS", "frontendBuild")
    require(failures, frontend_unit == "PASS", "frontendUnit")
    require(failures, java_targeted == "PASS", "javaTargeted")
    require(failures, cases.get("runtimeHealth") == "PASS", "runtimeHealth")
    require(failures, cases.get("overview") == "PASS", "overview")
    require(failures, cases.get("runList") == "PASS", "runList")
    require(failures, cases.get("runListFields") == "PASS", "runListFields")
    require(failures, cases.get("runDetail") == "PASS", "runDetail")
    require(failures, cases.get("evidenceTimeline") == "PASS", "evidenceTimeline")
    require(failures, cases.get("overrideValidation") == "PASS", "overrideValidation")
    require(failures, cases.get("override") == "PASS", "override")
    require(failures, cases.get("replay") == "PASS", "replay")
    require(failures, cases.get("compare") == "PASS", "compare")
    require(failures, cases.get("permissionNoTokenRejected") == "PASS", "permissionNoTokenRejected")
    require(failures, summary.get("tenantViolations") == 0, "tenantViolations")
    require(failures, summary.get("permissionViolations") == 0, "permissionViolations")
    require(failures, summary.get("evidenceSensitiveLeakCount") == 0, "evidenceSensitiveLeakCount")
    require(failures, summary.get("apiFailed") == 0, "apiFailed")
    require(failures, summary.get("overridePreservedOriginal") is True, "overridePreservedOriginal")
    require(failures, summary.get("replayCreatedNewRun") is True, "replayCreatedNewRun")

    if failures:
        print("AGENT_RAG_ADMIN_OPERATIONS_FAIL")
        print(json.dumps({"failures": failures}, ensure_ascii=False))
        return 1

    for token in PASS_TOKENS:
        print(token)
    print("MODEL_RERANKER_NOT_VERIFIED")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")
    return 0


def require(failures: list[str], condition: bool, name: str) -> None:
    if not condition:
        failures.append(name)


if __name__ == "__main__":
    raise SystemExit(main())
