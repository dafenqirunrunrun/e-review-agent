from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol


class SpanHandle(Protocol):
    """Small runtime-span surface shared by workflows and infrastructure."""

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None: ...


class WorkflowObserver(Protocol):
    """Request-scoped observer; implementations must never affect business flow."""

    def span(
        self,
        name: str,
        kind: str = "span",
        *,
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[SpanHandle]: ...


class NoopSpan:
    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> None:
        return None


class NoopWorkflowObserver:
    def span(
        self,
        name: str,
        kind: str = "span",
        *,
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[SpanHandle]:
        return _NoopSpanContext()


class _NoopSpanContext(AbstractContextManager[SpanHandle]):
    def __enter__(self) -> SpanHandle:
        return NoopSpan()

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        return False
