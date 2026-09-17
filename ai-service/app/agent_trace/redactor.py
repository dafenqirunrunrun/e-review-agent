from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.agent_trace.hash_service import TraceHashService


class AgentTraceRedactor:
    DENYLIST = {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "api_key",
        "apikey",
        "private_key",
        "email",
        "phone",
        "mobile",
        "id_card",
        "bank_card",
    }

    ABSOLUTE_PATH_RE = re.compile(r"([A-Za-z]:\\|/home/|/Users/|\\\\)")

    def __init__(
        self,
        hash_service: TraceHashService,
        max_list_items: int = 100,
        max_error_message_length: int = 512,
    ):
        self.hash_service = hash_service
        self.max_list_items = max_list_items
        self.max_error_message_length = max_error_message_length

    def summarize(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            output: dict[str, Any] = {}
            for key, item in value.items():
                normalized_key = str(key).lower().replace("-", "_")
                if normalized_key in self.DENYLIST or any(part in normalized_key for part in self.DENYLIST):
                    output[str(key)] = {"hmacSha256": self.hash_service.hash_sensitive_text(str(item))}
                else:
                    output[str(key)] = self.summarize(item)
            return output
        if isinstance(value, str):
            return self._summarize_text(value)
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            items = list(value)
            summarized = [self.summarize(item) for item in items[: self.max_list_items]]
            if len(items) > self.max_list_items:
                summarized.append({"truncated": True, "originalCount": len(items)})
            return summarized
        return value

    def _summarize_text(self, value: str) -> dict[str, Any]:
        safe = value[: self.max_error_message_length]
        return {
            "length": len(value),
            "hmacSha256": self.hash_service.hash_sensitive_text(value),
            "containsAbsolutePath": bool(self.ABSOLUTE_PATH_RE.search(safe)),
            "truncated": len(value) > self.max_error_message_length,
        }
