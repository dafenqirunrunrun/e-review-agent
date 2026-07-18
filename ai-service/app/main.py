from fastapi import FastAPI

from app.api.agent_framework import router as agent_framework_router
from app.api.enterprise_e_review import router as enterprise_e_review_router
from app.api.llm import router as llm_router
from app.api.rag_v2 import router as rag_v2_router
from app.api.review import router as review_router
from app.api.system import router as system_router
from app.api.vlm import router as vlm_router
from app.core.config import settings


app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    description="Mock multimodal review sentiment analysis service for E-Review Agent.",
)

app.include_router(review_router, prefix=settings.api_prefix)
app.include_router(enterprise_e_review_router, prefix=settings.api_prefix)
app.include_router(agent_framework_router, prefix=settings.api_prefix)
app.include_router(llm_router, prefix=settings.api_prefix)
app.include_router(rag_v2_router, prefix=settings.api_prefix)
app.include_router(vlm_router, prefix=settings.api_prefix)
app.include_router(system_router, prefix=settings.api_prefix)


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": settings.service_name}
