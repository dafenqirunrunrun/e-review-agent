from fastapi import APIRouter

from app.policy_rag.playground import PolicyEvidencePlayground, PolicyPlaygroundRequest


router = APIRouter(prefix="/policy/playground", tags=["policy-playground"])
playground = PolicyEvidencePlayground()


@router.post("/query")
def query_policy_evidence(payload: PolicyPlaygroundRequest):
    return playground.query(payload)
