from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Protocol

from app.agent_trace.contracts import AgentExecutionTrace, AgentTraceEvent


class AgentTraceSink(Protocol):
    def start_trace(self, trace: AgentExecutionTrace) -> None: ...
    def append_event(self, event: AgentTraceEvent) -> None: ...
    def complete_trace(self, trace: AgentExecutionTrace) -> None: ...
    def fail_trace(self, trace: AgentExecutionTrace, reason: str) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


class NullTraceSink:
    def start_trace(self, trace: AgentExecutionTrace) -> None:
        return None

    def append_event(self, event: AgentTraceEvent) -> None:
        return None

    def complete_trace(self, trace: AgentExecutionTrace) -> None:
        return None

    def fail_trace(self, trace: AgentExecutionTrace, reason: str) -> None:
        return None

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class InMemoryTraceSink:
    def __init__(self) -> None:
        self.traces: list[AgentExecutionTrace] = []
        self.events: list[AgentTraceEvent] = []

    def start_trace(self, trace: AgentExecutionTrace) -> None:
        self.traces.append(trace)

    def append_event(self, event: AgentTraceEvent) -> None:
        self.events.append(event)

    def complete_trace(self, trace: AgentExecutionTrace) -> None:
        self.traces[-1] = trace

    def fail_trace(self, trace: AgentExecutionTrace, reason: str) -> None:
        self.traces[-1] = trace

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class JsonlTraceSink:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tmp_path: Path | None = None
        self._final_path: Path | None = None
        self._handle = None

    def start_trace(self, trace: AgentExecutionTrace) -> None:
        trace_id = trace.traceHeader.traceId
        self._tmp_path = self.output_dir / f"{trace_id}.{uuid.uuid4().hex}.jsonl.incomplete"
        self._final_path = self.output_dir / f"{trace_id}.jsonl"
        self._handle = self._tmp_path.open("w", encoding="utf-8")
        self._write({"recordType": "header", "payload": trace.traceHeader.to_dict()})

    def append_event(self, event: AgentTraceEvent) -> None:
        self._write({"recordType": "event", "payload": event.to_dict()})

    def complete_trace(self, trace: AgentExecutionTrace) -> None:
        self._write({"recordType": "footer", "payload": trace.traceFooter.to_dict() if trace.traceFooter else None})
        self.flush()
        self.close()
        assert self._tmp_path is not None and self._final_path is not None
        os.replace(self._tmp_path, self._final_path)

    def fail_trace(self, trace: AgentExecutionTrace, reason: str) -> None:
        self._write({"recordType": "incomplete", "reason": reason, "payload": trace.to_dict()})
        self.flush()
        self.close()

    def flush(self) -> None:
        if self._handle:
            self._handle.flush()
            os.fsync(self._handle.fileno())

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None

    def _write(self, value: dict) -> None:
        if not self._handle:
            raise RuntimeError("trace file is not open")
        self._handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
