from __future__ import annotations

import threading

from app.policy_rag.retriever import PolicyEvidenceRetriever


_lock = threading.Lock()
_retriever: PolicyEvidenceRetriever | None = None


def get_runtime_policy_retriever() -> PolicyEvidenceRetriever:
    """Return the process-wide retriever used by review and playground traffic."""
    global _retriever
    if _retriever is not None:
        return _retriever
    with _lock:
        if _retriever is None:
            _retriever = PolicyEvidenceRetriever()
        return _retriever
