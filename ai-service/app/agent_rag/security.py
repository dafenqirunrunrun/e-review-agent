from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

from app.platform.security import PIIRedactor, PromptInjectionGuard


SENSITIVE_KEYS = {"password", "token", "secret", "cookie", "authorization", "api_key", "apikey"}


@dataclass(frozen=True)
class AgentRagSecurityConfig:
    pii_redaction_enabled: bool = True
    prompt_injection_guard_enabled: bool = True
    prompt_injection_action: str = "manual-review"
    audit_retention_days: int = 30
    secure_export_enabled: bool = True


@dataclass(frozen=True)
class AgentRagSecurityDecision:
    originalHash: str
    sanitizedHash: str
    sanitizedQuery: str
    piiRedactionCount: int = 0
    promptInjectionDetected: bool = False
    promptInjectionAction: str = "none"
    promptInjectionMatchCount: int = 0
    governanceStatus: str = "pass"
    sanitizedContext: dict[str, Any] = field(default_factory=dict)


def load_agent_rag_security_config(env: dict[str, str] | None = None) -> AgentRagSecurityConfig:
    source = env or os.environ
    return AgentRagSecurityConfig(
        pii_redaction_enabled=source.get("RAG_PII_REDACTION_ENABLED", "true").lower() == "true",
        prompt_injection_guard_enabled=source.get("RAG_PROMPT_INJECTION_GUARD_ENABLED", "true").lower() == "true",
        prompt_injection_action=source.get("RAG_PROMPT_INJECTION_ACTION", "manual-review").strip() or "manual-review",
        audit_retention_days=max(1, int(source.get("RAG_AUDIT_RETENTION_DAYS", "30") or "30")),
        secure_export_enabled=source.get("RAG_SECURE_EXPORT_ENABLED", "true").lower() == "true",
    )


class AgentRagSecurityGovernor:
    def __init__(self, config: AgentRagSecurityConfig | None = None):
        self.config = config or load_agent_rag_security_config()
        self._redactor = PIIRedactor()
        self._guard = PromptInjectionGuard()

    def inspect(self, query: str, context: dict[str, Any] | None = None) -> AgentRagSecurityDecision:
        sanitized_query = query
        redaction_count = 0
        if self.config.pii_redaction_enabled:
            sanitized_query, redaction_count = self._redactor.redact(query)
        guard = {"blocked": False, "matches": []}
        if self.config.prompt_injection_guard_enabled:
            guard = self._guard.inspect(sanitized_query)
        detected = bool(guard["blocked"])
        return AgentRagSecurityDecision(
            originalHash=_stable_hash(query),
            sanitizedHash=_stable_hash(sanitized_query),
            sanitizedQuery=sanitized_query,
            piiRedactionCount=redaction_count,
            promptInjectionDetected=detected,
            promptInjectionAction=self.config.prompt_injection_action if detected else "none",
            promptInjectionMatchCount=len(guard.get("matches") or []),
            governanceStatus="blocked" if detected else "redacted" if redaction_count else "pass",
            sanitizedContext=sanitize_context(context or {}, self._redactor),
        )


def sanitize_context(context: dict[str, Any], redactor: PIIRedactor | None = None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    pii = redactor or PIIRedactor()
    for key, value in context.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in SENSITIVE_KEYS):
            safe[str(key)] = "[REDACTED]"
            continue
        if isinstance(value, str):
            safe[str(key)] = pii.redact(value)[0]
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[str(key)] = value
        else:
            safe[str(key)] = "[structured-context-redacted]"
    return safe


def secure_export_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redactor = PIIRedactor()
    return sanitize_context(payload, redactor)


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:24]
