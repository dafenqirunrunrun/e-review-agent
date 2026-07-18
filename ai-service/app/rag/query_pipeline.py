from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.platform.security import PromptInjectionGuard


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    rewrites: list[str]
    intent: str
    entities: list[str]
    keywords: list[str]
    filters: dict[str, str] = field(default_factory=dict)
    blocked: bool = False
    block_reason: str | None = None


class QueryPipeline:
    def plan(self, query: str) -> QueryPlan:
        normalized = unicodedata.normalize("NFKC", query).strip()
        lowered = normalized.lower()
        guard = PromptInjectionGuard().inspect(normalized)
        if guard["blocked"]:
            return QueryPlan(normalized, [normalized], "blocked", [], [], blocked=True, block_reason="PROMPT_INJECTION_DETECTED")
        intent = "after_sales" if any(word in lowered for word in ["refund", "return", "退货", "退款", "售后"]) else "review_risk"
        entities = re.findall(r"[A-Z]{2,}-?\d+|[\u4e00-\u9fff]{2,}", normalized)[:8]
        keywords = [item.lower() for item in re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", normalized)[:12]]
        rewrites = [normalized]
        lexical = " ".join(keywords[:8])
        if lexical and lexical != normalized:
            rewrites.append(lexical)
        semantic = f"{intent} {' '.join(entities[:4])}".strip()
        if semantic and semantic not in rewrites:
            rewrites.append(semantic)
        return QueryPlan(normalized, rewrites[:3], intent, entities, keywords)
