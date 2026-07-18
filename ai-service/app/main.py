import os
import time
import uuid

from fastapi import FastAPI, Request

from app.api.agent_framework import router as agent_framework_router
from app.api.enterprise_e_review import router as enterprise_e_review_router
from app.api.llm import router as llm_router
from app.api.rag_v2 import router as rag_v2_router
from app.api.review import router as review_router
from app.api.system import router as system_router
from app.api.vlm import router as vlm_router
from app.core.config import settings
from app.observability import REQUEST_ID_HEADER, record_http, snapshot


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


@app.middleware("http")
async def public_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.time()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = int((time.time() - started_at) * 1000)
        record_http(request_id, request.url.path, status_code, duration_ms)
        if "response" in locals():
            response.headers[REQUEST_ID_HEADER] = request_id


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": settings.service_name}


def _public_runtime_status(status: str) -> dict:
    runtime_mode = os.getenv("AI_RUNTIME_MODE", "public-rule")
    return {
        "status": status,
        "service": settings.service_name,
        "runtimeMode": runtime_mode,
        "engineType": "rule" if runtime_mode == "public-rule" else runtime_mode,
        "modelLoaded": False,
        "privateAssetsRequired": False,
        "schemaVersion": os.getenv("AI_SCHEMA_VERSION", "2.0.0"),
    }


@app.get("/health/live")
def live():
    return _public_runtime_status("live")


@app.get("/health/ready")
def ready():
    return _public_runtime_status("ready")


@app.get("/metrics")
def metrics():
    return {"service": settings.service_name, "status": "ok", "metrics": snapshot()}
