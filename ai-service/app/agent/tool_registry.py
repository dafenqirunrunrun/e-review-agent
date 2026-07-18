from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    json_schema: dict[str, Any]
    timeout_ms: int
    risk_level: str
    idempotent: bool
    retry_policy: dict[str, Any]
    audit_policy: str
    tenant_scope: str
    output_sanitizer: str
    handler: Callable[..., Any] | None = None


class ToolRegistry:
    ALLOWED = {
        "search_cases",
        "search_policy",
        "get_review_context",
        "validate_schema",
        "verify_evidence",
        "route_human_review",
    }

    FORBIDDEN_BUSINESS_ACTIONS = {"refund", "ban_user", "compensate", "delete_review", "ship_order"}

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        for name in self.ALLOWED:
            self.register(
                ToolDefinition(
                    name=name,
                    json_schema={"type": "object", "additionalProperties": True},
                    timeout_ms=5000,
                    risk_level="read_only",
                    idempotent=True,
                    retry_policy={"max_retries": 1},
                    audit_policy="aggregate_only",
                    tenant_scope="required",
                    output_sanitizer="hash_or_summary_only",
                )
            )

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self.FORBIDDEN_BUSINESS_ACTIONS or tool.risk_level != "read_only":
            raise ValueError("business write tools are forbidden")
        if tool.name not in self.ALLOWED:
            raise ValueError(f"tool {tool.name} is not allowlisted")
        if tool.timeout_ms <= 0 or tool.timeout_ms > 60000:
            raise ValueError("tool timeout must be bounded")
        if tool.tenant_scope != "required":
            raise ValueError("tool tenant scope is required")
        if tool.audit_policy != "aggregate_only":
            raise ValueError("tool audit policy must be aggregate_only")
        if tool.output_sanitizer != "hash_or_summary_only":
            raise ValueError("tool output sanitizer must be hash_or_summary_only")
        if not tool.idempotent:
            raise ValueError("tool must be idempotent")
        if int(tool.retry_policy.get("max_retries", 0)) > 2:
            raise ValueError("tool retry policy is too broad")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"tool {name} is not registered")
        return self._tools[name]

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "timeout_ms": tool.timeout_ms,
                "risk_level": tool.risk_level,
                "idempotent": tool.idempotent,
                "tenant_scope": tool.tenant_scope,
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]
