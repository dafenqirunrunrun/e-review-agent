from fastapi import APIRouter

from app.data_governance.research_scope_gate import private_research_status


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/readiness")
def readiness():
    return private_research_status()
