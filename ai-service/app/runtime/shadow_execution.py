from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

from app.llm.enterprise_providers import EnterpriseTextRequest, EnterpriseTextResult


@dataclass(frozen=True)
class ShadowAggregate:
    request_hash: str
    base_schema_valid: bool
    adapter_schema_valid: bool
    base_fallback: bool
    adapter_fallback: bool
    risk_type_agreement: bool
    risk_level_agreement: bool
    human_review_agreement: bool
    latency_ms: int
    memory_mb: int | None = None
    error_code: str | None = None


class ShadowExecutionQueue:
    def __init__(self, maxsize: int = 2):
        if maxsize > 2:
            raise ValueError("shadow queue size must not exceed 2 by default policy")
        self.queue: asyncio.Queue[Callable[[], Awaitable[ShadowAggregate]]] = asyncio.Queue(maxsize=maxsize)
        self.dropped_count = 0
        self.completed: list[ShadowAggregate] = []

    @property
    def depth(self) -> int:
        return self.queue.qsize()

    async def submit(self, task: Callable[[], Awaitable[ShadowAggregate]]) -> bool:
        try:
            self.queue.put_nowait(task)
            return True
        except asyncio.QueueFull:
            self.dropped_count += 1
            return False

    async def drain_once(self) -> ShadowAggregate | None:
        if self.queue.empty():
            return None
        task = await self.queue.get()
        try:
            result = await task()
            self.completed.append(result)
            return result
        finally:
            self.queue.task_done()


def aggregate_shadow_result(
    request: EnterpriseTextRequest,
    base: EnterpriseTextResult,
    adapter: EnterpriseTextResult,
    started_at: float | None = None,
    error_code: str | None = None,
) -> ShadowAggregate:
    latency_ms = 0 if started_at is None else round((time.perf_counter() - started_at) * 1000)
    request_hash = hashlib.sha256(request.request_hash.encode("utf-8")).hexdigest()[:24]
    return ShadowAggregate(
        request_hash=request_hash,
        base_schema_valid=base.schema_valid,
        adapter_schema_valid=adapter.schema_valid,
        base_fallback=base.fallback_used,
        adapter_fallback=adapter.fallback_used,
        risk_type_agreement=base.decision.risk_type == adapter.decision.risk_type,
        risk_level_agreement=base.decision.risk_level == adapter.decision.risk_level,
        human_review_agreement=base.decision.need_human_review == adapter.decision.need_human_review,
        latency_ms=latency_ms,
        error_code=error_code,
    )
