import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from app.llm.config import ProviderConfig


@dataclass
class ProviderResult:
    content: str
    token_usage_input: Optional[int]
    token_usage_output: Optional[int]
    latency_ms: int


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def complete_json(self, prompt: str) -> ProviderResult:
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            started = time.perf_counter()
            try:
                headers = {"Content-Type": "application/json"}
                if self.config.api_key:
                    headers["Authorization"] = f"Bearer {self.config.api_key}"
                response = httpx.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.config.model_name,
                        "messages": [
                            {"role": "system", "content": "你是电商评论治理助手。必须只返回合法 JSON。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                usage: Dict[str, Any] = body.get("usage") or {}
                return ProviderResult(
                    content=content,
                    token_usage_input=usage.get("prompt_tokens"),
                    token_usage_output=usage.get("completion_tokens"),
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
            except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
        raise RuntimeError(f"LLM provider request failed: {type(last_error).__name__}") from last_error
