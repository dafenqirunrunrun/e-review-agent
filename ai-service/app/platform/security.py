from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


class PromptInjectionGuard:
    PATTERNS = [
        re.compile(r"ignore previous instructions", re.I),
        re.compile(r"ignore (all )?(system|developer|safety) instructions", re.I),
        re.compile(r"system prompt", re.I),
        re.compile(r"tool call", re.I),
        re.compile(r"disable safety", re.I),
        re.compile(r"reveal (the )?(system|developer) prompt", re.I),
        re.compile(r"delete (all )?(negative )?reviews?", re.I),
        re.compile(r"bypass (approval|human review|guardrail)", re.I),
        re.compile(r"忽略.{0,8}(系统|安全|开发者|指令)"),
        re.compile(r"(泄露|输出|打印).{0,8}(系统提示|system prompt|开发者提示)"),
        re.compile(r"(删除|清空|篡改).{0,8}(差评|评论|数据库|记录)"),
    ]

    def inspect(self, text: str) -> dict:
        matched = [pattern.pattern for pattern in self.PATTERNS if pattern.search(text)]
        return {"blocked": bool(matched), "matches": matched, "source_trust_delta": "downgrade" if matched else "none"}


class SourceTrustPolicy:
    LEVELS = ["external_untrusted", "synthetic", "internal_unverified", "internal_verified"]

    def can_support_high_risk(self, trust_level: str) -> bool:
        return trust_level == "internal_verified"

    def label_retrieved_content(self, text: str) -> str:
        return f"UNTRUSTED_RETRIEVED_CONTENT:{hashlib.sha256(text.encode()).hexdigest()[:16]}"


class PIIRedactor:
    PATTERNS = [
        re.compile(r"1[3-9]\d{9}"),
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        re.compile(r"\b\d{15}(\d{2}[0-9Xx])?\b"),
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
        re.compile(r"(api[_-]?key|token|cookie)\s*[:=]\s*[A-Za-z0-9._-]+", re.I),
        re.compile(r"bearer\s+[A-Za-z0-9._=-]{16,}", re.I),
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ]

    def redact(self, text: str) -> tuple[str, int]:
        count = 0
        redacted = text
        for pattern in self.PATTERNS:
            redacted, n = pattern.subn("[REDACTED]", redacted)
            count += n
        return redacted, count


@dataclass(frozen=True)
class SafeStructuredLogger:
    def event(self, **kwargs) -> dict:
        allowed = {
            "trace_id",
            "request_id",
            "tenant_hash",
            "input_hash",
            "route",
            "retrieval_count",
            "model_mode",
            "tool_names",
            "latency_ms",
            "error_code",
            "schema_status",
            "fallback_status",
        }
        return {key: value for key, value in kwargs.items() if key in allowed}
