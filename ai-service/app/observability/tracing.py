from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    started_at: float = field(default_factory=time.perf_counter)
    ended_at: float | None = None
    attributes: dict | None = None

    def finish(self, **attributes) -> "Span":
        self.ended_at = time.perf_counter()
        self.attributes = attributes
        return self

    @property
    def latency_ms(self) -> int:
        end = self.ended_at or time.perf_counter()
        return round((end - self.started_at) * 1000)


class TraceRecorder:
    REQUIRED_SPANS = [
        "request",
        "input_guard",
        "route",
        "query_rewrite",
        "sparse_retrieval",
        "dense_retrieval",
        "fusion",
        "rerank",
        "evidence_verify",
        "model_generate",
        "policy_guard",
        "response",
        "audit",
    ]

    def __init__(self):
        self.spans: list[Span] = []

    def start(self, name: str) -> Span:
        span = Span(name)
        self.spans.append(span)
        return span

    def coverage(self) -> dict[str, bool]:
        present = {span.name for span in self.spans}
        return {name: name in present for name in self.REQUIRED_SPANS}
