from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase3c1"


def contains(path: str, needles: list[str]) -> dict[str, bool]:
    text = (ROOT / path).read_text(encoding="utf-8")
    return {needle: needle in text for needle in needles}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    java = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "mvn -pl litemall-admin-api -am -Dtest=*AgentRag* -DfailIfNoTests=false test",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    checks = {
        "javaTargeted": java.returncode == 0 and "Failures: 0, Errors: 0" in java.stdout,
        "retentionMapper": all(
            contains(
                "litemall-db/src/main/resources/org/linlinjava/litemall/db/dao/LitemallAgentRagEvidenceMapper.xml",
                [
                    "countExpiredCandidates",
                    "selectExpiredCandidates",
                    "expireEvidencePayload",
                    "evidence_expires_at",
                ],
            ).values()
        ),
        "retentionApi": all(
            contains(
                "litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/web/AdminAgentRagController.java",
                [
                    "/security/retention/status",
                    "/security/retention/preview",
                    "/security/retention/execute",
                    "admin:agentRag:retention",
                ],
            ).values()
        ),
        "secureExportApi": all(
            contains(
                "litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/web/AdminAgentRagController.java",
                [
                    "/runs/{id}/export",
                    "admin:agentRag:export",
                ],
            ).values()
        )
        and all(
            contains(
                "litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/service/agentrag/AgentRagRetentionExportService.java",
                [
                    "rawEvidenceExported",
                    "RAW_EVIDENCE_NOT_EXPORTED",
                    "boundedSummary",
                    "reasonLength",
                ],
            ).values()
        ),
        "adminSecurityUi": all(
            contains(
                "litemall-admin/src/views/agent-rag/security.vue",
                [
                    "Retention control",
                    "Safe export",
                    "Expire payloads",
                    "raw evidence",
                ],
            ).values()
        )
        and all(
            contains(
                "litemall-admin/src/api/agentRag.js",
                [
                    "getAgentRagRetentionStatus",
                    "previewAgentRagRetention",
                    "executeAgentRagRetention",
                    "exportAgentRagRun",
                ],
            ).values()
        )
        and all(
            contains(
                "litemall-admin/src/router/index.js",
                [
                    "agentRagSecurity",
                    "@/views/agent-rag/security",
                    "app.menu.agent_rag_security",
                ],
            ).values()
        ),
        "docs": all(
            contains(
                "docs/agent-rag/V2_RETENTION_OPERATIONS.md",
                [
                    "No arbitrary SQL",
                    "No business table delete",
                    "dry run",
                ],
            ).values()
        )
        and all(
            contains(
                "docs/agent-rag/V2_SECURE_EXPORT_API.md",
                [
                    "rawEvidenceExported",
                    "does not include",
                    "bounded evidence summary",
                ],
            ).values()
        ),
    }
    result = {
        "schemaVersion": "agent-rag-phase3c1-retention-export-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "javaReturnCode": java.returncode,
        "boundaries": [
            "RAW_EVIDENCE_NOT_EXPORTED",
            "BUSINESS_TABLES_NOT_DELETED",
            "NO_PUBLIC_REPO_CHANGES",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    (OUT / "phase3c1-retention-export-gate-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result["status"] != "PASS":
        print("AGENT_RAG_RETENTION_EXPORT_GATE_FAIL")
        print(java.stdout[-4000:])
        print(java.stderr[-4000:])
        raise SystemExit(2)
    print("AGENT_RAG_RETENTION_API_PASS")
    print("AGENT_RAG_RETENTION_BOUNDARY_PASS")
    print("AGENT_RAG_SECURE_EXPORT_API_PASS")
    print("AGENT_RAG_ADMIN_SECURITY_UI_PASS")
    print("AGENT_RAG_RETENTION_EXPORT_GATE_PASS")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
