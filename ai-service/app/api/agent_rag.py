from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.observability import request_context
from app.agent_rag.runtime import AgentRagRuntime


router = APIRouter(prefix="/agent-rag", tags=["agent-rag"])


@router.post("/analyze")
def analyze(payload: AgentRagRequest, x_request_id: str | None = Header(default=None)):
    if x_request_id and x_request_id != payload.requestId:
        raise HTTPException(status_code=400, detail="AGENT_RAG_REQUEST_ID_HEADER_MISMATCH")
    with request_context(requestId=payload.requestId, tenantId=payload.tenantId, subjectId=payload.subjectId):
        result, _ = _runtime().analyze(payload)
    return result.model_dump(mode="json")


@lru_cache(maxsize=1)
def _runtime() -> AgentRagRuntime:
    fixture = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "agent_rag" / "phase1_cases.json"
    chunks = json.loads(fixture.read_text(encoding="utf-8"))["chunks"]
    runtime_chunks = []
    for row in chunks:
        runtime_chunks.append(row)
        if row.get("tenant_id") == "tenant-a":
            local_row = dict(row)
            local_row["tenant_id"] = "__local__"
            local_row["chunk_id"] = "__local__-" + str(row["chunk_id"])
            local_row["document_id"] = "__local__-" + str(row["document_id"])
            runtime_chunks.append(local_row)
    return AgentRagRuntime(chunks=runtime_chunks)
