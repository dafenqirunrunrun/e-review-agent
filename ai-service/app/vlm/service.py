import threading
from typing import Dict, Optional

from pydantic import ValidationError

from app.vlm.config import VlmConfig, load_config
from app.vlm.provider import LocalQwen3VlProvider
from app.vlm.schemas import (
    TextImageConsistencyRequest,
    VisualEvidenceResult,
    VlmSmokeResponse,
    VlmStatus,
)


_VLM_SEMAPHORE = threading.BoundedSemaphore(max(1, load_config().max_concurrency))


class VlmService:
    def __init__(self, config: Optional[VlmConfig] = None):
        self.config = config or load_config()
        self.provider = LocalQwen3VlProvider(self.config)

    def status(self) -> VlmStatus:
        return self.provider.status()

    def analyze(self, payload: Dict) -> VisualEvidenceResult:
        acquired = _VLM_SEMAPHORE.acquire(timeout=max(1, self.config.queue_timeout_seconds))
        if not acquired:
            raise RuntimeError("VLM_QUEUE_TIMEOUT")
        try:
            return self.provider.analyze_images(payload)
        finally:
            _VLM_SEMAPHORE.release()

    def consistency(self, payload: TextImageConsistencyRequest) -> Dict:
        result = payload.visual_result
        if not result.image_available or result.image_quality in {"irrelevant", "uncertain"}:
            consistency = "uncertain"
        else:
            consistency = result.text_image_consistency
        return {
            "text_image_consistency": consistency,
            "need_human_review": consistency in {"conflicting", "uncertain"},
            "visual_evidence_count": len(result.visual_evidence),
        }

    @staticmethod
    def validate_schema(payload: Dict) -> Dict:
        try:
            result = VisualEvidenceResult.model_validate(payload)
            return {"schema_valid": True, "result": result.model_dump()}
        except ValidationError as exc:
            return {"schema_valid": False, "errors": exc.errors()}

    def smoke_test(self) -> VlmSmokeResponse:
        status = self.status()
        if not status.model_available:
            return VlmSmokeResponse(
                marker="MULTIMODAL_VLM_EVAL_BLOCKED",
                status=status,
                schema_valid=True,
                message="VLM_MODEL_NOT_AVAILABLE; place Qwen3-VL-2B-Instruct outside Git and rerun smoke test.",
            )
        return VlmSmokeResponse(
            marker="MULTIMODAL_VLM_PILOT_READY",
            status=status,
            schema_valid=True,
            message="Model files are present; real image smoke inference still must be executed before PASS.",
        )


_SERVICE: Optional[VlmService] = None


def vlm_service() -> VlmService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = VlmService()
    return _SERVICE
