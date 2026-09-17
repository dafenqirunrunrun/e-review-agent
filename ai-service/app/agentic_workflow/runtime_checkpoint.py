"""Durable local checkpoints for the review workflow; no new service dependency."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ReviewWorkflowState(str, Enum):
    CREATED = "CREATED"
    ROUTING = "ROUTING"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    REFLECTION = "REFLECTION"
    DECISION = "DECISION"
    WAIT_HUMAN = "WAIT_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS = {
    ReviewWorkflowState.CREATED: {ReviewWorkflowState.ROUTING, ReviewWorkflowState.FAILED},
    ReviewWorkflowState.ROUTING: {ReviewWorkflowState.RISK_ANALYSIS, ReviewWorkflowState.FAILED},
    ReviewWorkflowState.RISK_ANALYSIS: {ReviewWorkflowState.EVIDENCE_RETRIEVAL, ReviewWorkflowState.DECISION, ReviewWorkflowState.WAIT_HUMAN, ReviewWorkflowState.FAILED},
    ReviewWorkflowState.EVIDENCE_RETRIEVAL: {ReviewWorkflowState.REFLECTION, ReviewWorkflowState.FAILED},
    ReviewWorkflowState.REFLECTION: {ReviewWorkflowState.EVIDENCE_RETRIEVAL, ReviewWorkflowState.DECISION, ReviewWorkflowState.WAIT_HUMAN, ReviewWorkflowState.FAILED},
    ReviewWorkflowState.DECISION: {ReviewWorkflowState.COMPLETED, ReviewWorkflowState.WAIT_HUMAN, ReviewWorkflowState.FAILED},
    ReviewWorkflowState.WAIT_HUMAN: set(),
    ReviewWorkflowState.COMPLETED: set(),
    ReviewWorkflowState.FAILED: set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


@dataclass
class NodeExecutionRecord:
    nodeName: str
    startTime: str
    endTime: str = ""
    status: str = "RUNNING"
    inputHash: str = ""
    outputHash: str = ""
    errorMessage: str = ""
    retryCount: int = 0
    retryReason: str = ""


@dataclass
class WorkflowCheckpoint:
    id: str
    reviewId: str
    workflowVersion: str = "review-agentic-v1"
    currentState: str = ReviewWorkflowState.CREATED.value
    completedNodes: list[str] = field(default_factory=list)
    failedNode: str = ""
    retryCount: int = 0
    memorySnapshot: dict[str, Any] = field(default_factory=dict)
    governanceSnapshot: dict[str, Any] = field(default_factory=dict)
    nodeExecutions: list[NodeExecutionRecord] = field(default_factory=list)
    nodeOutputs: dict[str, Any] = field(default_factory=dict)
    createdAt: str = field(default_factory=_now)
    updatedAt: str = field(default_factory=_now)


class CheckpointCorruptError(RuntimeError):
    pass


class SimulatedWorkflowCrash(RuntimeError):
    pass


class FileWorkflowCheckpointStore:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or Path(__file__).resolve().parents[2] / "data" / "workflow_checkpoints")

    def load(self, review_id: str) -> WorkflowCheckpoint | None:
        path = self._path(review_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = [NodeExecutionRecord(**item) for item in raw.pop("nodeExecutions", [])]
            return WorkflowCheckpoint(nodeExecutions=records, **raw)
        except Exception as exc:
            raise CheckpointCorruptError("WORKFLOW_CHECKPOINT_CORRUPT") from exc

    def save(self, checkpoint: WorkflowCheckpoint) -> WorkflowCheckpoint:
        self.root.mkdir(parents=True, exist_ok=True)
        checkpoint.updatedAt = _now()
        payload = asdict(checkpoint)
        path = self._path(checkpoint.reviewId)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return checkpoint

    def _path(self, review_id: str) -> Path:
        safe = hashlib.sha256(review_id.encode("utf-8")).hexdigest()
        return self.root / f"{safe}.json"


class WorkflowRuntime:
    def __init__(self, store: FileWorkflowCheckpointStore, review_id: str):
        self.store = store
        existing = store.load(review_id)
        self.checkpoint = existing or WorkflowCheckpoint(id=_hash({"reviewId": review_id, "createdAt": _now()})[:24], reviewId=review_id)
        if existing is None:
            self.store.save(self.checkpoint)

    def transition(self, target: ReviewWorkflowState) -> None:
        current = ReviewWorkflowState(self.checkpoint.currentState)
        if target == current:
            return
        if target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"ILLEGAL_WORKFLOW_TRANSITION:{current.value}->{target.value}")
        self.checkpoint.currentState = target.value
        self.store.save(self.checkpoint)

    def completed(self, node: str) -> bool:
        return node in self.checkpoint.completedNodes

    def start_node(self, node: str, input_value: Any) -> None:
        if self.completed(node):
            return
        self.checkpoint.nodeExecutions.append(NodeExecutionRecord(nodeName=node, startTime=_now(), inputHash=_hash(input_value)))
        self.store.save(self.checkpoint)

    def finish_node(self, node: str, output: Any, *, memory: dict[str, Any] | None = None, governance: dict[str, Any] | None = None) -> None:
        record = next((item for item in reversed(self.checkpoint.nodeExecutions) if item.nodeName == node and item.status == "RUNNING"), None)
        if record is None:
            raise ValueError(f"WORKFLOW_NODE_NOT_STARTED:{node}")
        record.status, record.endTime, record.outputHash = "SUCCESS", _now(), _hash(output)
        self.checkpoint.completedNodes.append(node)
        self.checkpoint.nodeOutputs[node] = output
        if memory is not None:
            self.checkpoint.memorySnapshot = memory
        if governance is not None:
            self.checkpoint.governanceSnapshot = governance
        self.store.save(self.checkpoint)

    def fail_node(self, node: str, error: Exception, *, retryable: bool) -> bool:
        record = next((item for item in reversed(self.checkpoint.nodeExecutions) if item.nodeName == node and item.status == "RUNNING"), None)
        if record:
            record.status, record.endTime, record.errorMessage = "FAILED", _now(), str(error)[:240]
            record.retryReason = "temporary_failure" if retryable else "non_retryable_failure"
            record.retryCount += 1
        self.checkpoint.failedNode = node
        self.checkpoint.retryCount += 1
        self.store.save(self.checkpoint)
        return retryable and self.checkpoint.retryCount <= 2

    def final_response(self) -> dict[str, Any] | None:
        return self.checkpoint.governanceSnapshot.get("response") if self.checkpoint.currentState in {ReviewWorkflowState.COMPLETED.value, ReviewWorkflowState.WAIT_HUMAN.value} else None

    def finalize(self, response: dict[str, Any], target: ReviewWorkflowState, *, memory: dict[str, Any] | None = None) -> None:
        """Persist the terminal decision before exposing its terminal state."""
        if not self.completed("finalize"):
            self.start_node("finalize", {"state": target.value})
            self.finish_node("finalize", response, memory=memory, governance={"response": response})
        self.transition(target)
