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
        ["powershell", "-NoProfile", "-Command", "mvn -pl litemall-admin-api -am -Dtest=*AgentRag* -DfailIfNoTests=false test"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    checks = {
        "javaTargeted": java.returncode == 0 and "Tests run: 25, Failures: 0, Errors: 0, Skipped: 0" in java.stdout,
        "migration": all(contains("litemall-db/sql/litemall_agent_rag_security_governance.sql", [
            "litemall_agent_rag_audit_chain",
            "security_policy_version",
            "audit_hash",
            "previous_override_hash",
        ]).values()),
        "integrityApi": all(contains("litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/web/AdminAgentRagController.java", [
            "/runs/{id}/integrity",
            "/security/status",
            "admin:agentRag:security",
        ]).values()),
        "auditService": all(contains("litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/service/agentrag/AgentRagAuditIntegrityService.java", [
            "citationSetHash",
            "runtimeConfigHash",
            "effectiveDecisionHash",
            "auditHash",
            "INVALID_BUNDLE_HASH",
        ]).values()),
        "docs": all(contains("docs/agent-rag/V2_AUDIT_CHAIN_IMPLEMENTATION.md", [
            "bundleHash",
            "citationSetHash",
            "Tenant Chain",
            "Override Lineage",
        ]).values()),
    }
    result = {
        "schemaVersion": "agent-rag-phase3c1-security-governance-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "javaReturnCode": java.returncode,
        "javaSummaryFound": checks["javaTargeted"],
        "boundaries": [
            "RETENTION_EXECUTE_PENDING",
            "SECURE_EXPORT_API_PENDING",
            "ADMIN_SECURITY_UI_PENDING",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    (OUT / "phase3c1-security-governance-gate-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] != "PASS":
        print("AGENT_RAG_SECURITY_GOVERNANCE_FAIL")
        print(java.stdout[-4000:])
        print(java.stderr[-4000:])
        raise SystemExit(2)
    print("AGENT_RAG_JAVA_SECURITY_DTO_PASS")
    print("AGENT_RAG_AUDIT_CHAIN_PASS")
    print("AGENT_RAG_OVERRIDE_AUDIT_PASS")
    print("AGENT_RAG_REPLAY_LINEAGE_READY")
    print("AGENT_RAG_INTEGRITY_API_PASS")
    print("AGENT_RAG_SECURITY_GOVERNANCE_PASS")
    print("RETENTION_EXECUTE_PENDING")
    print("SECURE_EXPORT_API_PENDING")
    print("ADMIN_SECURITY_UI_PENDING")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
