import gc
import time
from typing import Dict
from pathlib import Path

from app.vlm.config import VlmConfig
from app.vlm.schemas import VisualEvidenceResult, VlmStatus
from app.vlm.qwen3_vl_runtime import Qwen3VlRuntime, Qwen3VlRuntimeRequest, Qwen3VlRuntimeSession
from app.vlm.schema_repair import parse_or_repair_visual_schema


class LocalQwen3VlProvider:
    model_name = "Qwen/Qwen3-VL-2B-Instruct"

    def __init__(self, config: VlmConfig):
        self.config = config
        self.loaded = False

    @property
    def available(self) -> bool:
        weights = [
            self.config.model_dir / "model.safetensors",
            self.config.model_dir / "pytorch_model.bin",
        ]
        return self.config.model_dir.is_dir() and (self.config.model_dir / "config.json").exists() and any(path.exists() for path in weights)

    def status(self) -> VlmStatus:
        return VlmStatus(
            provider=self.config.provider,
            model_name=self.model_name,
            model_dir=str(self.config.model_dir),
            model_available=self.available,
            device=self.config.device,
            dtype=self.config.dtype,
            load_in_4bit=self.config.load_in_4bit,
            max_images=self.config.max_images,
            max_pixels=self.config.max_pixels,
            min_pixels=self.config.min_pixels,
            lazy_load=self.config.lazy_load,
            unload_after_request=self.config.unload_after_request,
            memory_strategy=self.config.memory_strategy,
            loaded=self.loaded,
            blocked_reason=None if self.available else "VLM_MODEL_NOT_AVAILABLE",
        )

    def analyze_images(self, request: Dict, session: Qwen3VlRuntimeSession | None = None) -> VisualEvidenceResult:
        if not self.available:
            raise RuntimeError("VLM_MODEL_NOT_AVAILABLE")
        image_paths = [str(path) for path in request.get("image_paths") or [] if str(path).strip()]
        if not image_paths:
            raise RuntimeError("VLM_IMAGE_MISSING")
        if len(image_paths) > self.config.max_images:
            raise RuntimeError(f"VLM_IMAGE_COUNT_EXCEEDS_LIMIT:{self.config.max_images}")
        missing = [path for path in image_paths if not Path(path).exists()]
        if missing:
            raise RuntimeError(f"VLM_IMAGE_NOT_FOUND:{missing[0]}")

        prompt = self._prompt(request)
        if session is None:
            runtime_result = Qwen3VlRuntime().run(
                Qwen3VlRuntimeRequest(
                    image_paths=[image_paths[0]],
                    prompt=prompt,
                    model_dir=self.config.model_dir,
                    max_new_tokens=min(self.config.max_new_tokens, 48),
                    max_pixels=min(self.config.max_pixels, 147_456),
                    min_pixels=self.config.min_pixels,
                    do_sample=False,
                    stage="qwen3-vl-provider",
                    unload_after_request=self.config.unload_after_request,
                    min_free_memory_mb=5200,
                )
            )
        else:
            runtime_result = session.generate(
                image_paths=[image_paths[0]],
                prompt=prompt,
                max_new_tokens=min(self.config.max_new_tokens, 48),
                do_sample=False,
            )
        if runtime_result.error_code:
            detail = runtime_result.error_code
            if runtime_result.error_summary:
                detail = f"{detail}: {runtime_result.error_summary}"
            raise RuntimeError(detail)
        if not runtime_result.real_inference or not runtime_result.cuda_used or runtime_result.fallback_used:
            raise RuntimeError("VLM_REAL_INFERENCE_FAILED")

        parse_started = time.perf_counter()
        visual_result, repair_meta = parse_or_repair_visual_schema(runtime_result.raw_text)
        parse_or_repair_ms = round((time.perf_counter() - parse_started) * 1000, 2)
        mapping_started = time.perf_counter()
        payload = visual_result.model_dump()
        latency_breakdown = dict(runtime_result.latency_breakdown or {})
        latency_breakdown["raw_json_parse_ms"] = repair_meta.get("parse_ms", 0)
        latency_breakdown["deterministic_normalization_ms"] = repair_meta.get("normalization_ms", 0)
        latency_breakdown["schema_repair_ms"] = repair_meta.get("repair_ms", 0)
        latency_breakdown["parse_or_repair_total_ms"] = parse_or_repair_ms
        payload.update(
            {
                "provider_name": runtime_result.provider_name,
                "model_name": runtime_result.model_name,
                "real_inference": runtime_result.real_inference,
                "cuda_used": runtime_result.cuda_used,
                "fallback_used": runtime_result.fallback_used,
                "generate_executed": runtime_result.generate_executed,
                "schema_valid": True,
                "latency_ms": runtime_result.total_latency_ms,
                "model_load_ms": runtime_result.model_load_ms,
                "inference_ms": runtime_result.inference_ms,
                "gpu_peak_memory_mb": runtime_result.gpu_peak_memory_mb,
                "gpu_memory_after_unload_mb": runtime_result.gpu_memory_after_unload_mb,
                "input_token_count": runtime_result.input_token_count,
                "output_token_count": runtime_result.output_token_count,
                "latency_breakdown": latency_breakdown,
                "runtime_counters": runtime_result.runtime_counters,
                **repair_meta,
            }
        )
        payload["latency_breakdown"]["provider_mapping_ms"] = round((time.perf_counter() - mapping_started) * 1000, 2)
        return VisualEvidenceResult.model_validate(payload)

    @staticmethod
    def _prompt(request: Dict) -> str:
        review_text = str(request.get("review_text") or "")
        product_name = str(request.get("product_name") or "")
        return (
            "Return exactly one minified JSON object. No Markdown. No explanation. No extra keys. "
            "Use this complete schema and keep every key: "
            '{"image_available":true,"image_quality":"uncertain","ocr_text":[],"visual_findings":[],"package_damage_detected":false,'
            '"product_damage_detected":false,"leakage_detected":false,"missing_part_detected":false,'
            '"product_mismatch_detected":false,"privacy_risk_detected":false,"text_image_consistency":"uncertain",'
            '"visual_risk_level":"uncertain","visual_evidence":[],"unsupported_visual_claims":[],"need_human_review":false,'
            '"missing_information":[]}. '
            "Allowed image_quality: clear, blurred, occluded, irrelevant, uncertain. "
            "Allowed finding type: package_damage, product_damage, leakage, missing_part, product_mismatch, contamination, irrelevant, other. "
            "Allowed text_image_consistency: consistent, conflicting, unrelated, uncertain. "
            "Allowed visual_risk_level: low, medium, high, uncertain. "
            "Arrays must be [] when empty. Null is forbidden. Booleans must be true or false. "
            "Finding confidence must be a number from 0 to 1. Use uncertain when unsure. "
            "Only describe visible evidence. Do not infer damage from file names or review text. "
            "Do not output refund, compensation, or ban decisions. "
            f"Product name: {product_name[:200]}. Review text for consistency only: {review_text[:500]}"
        )

    @staticmethod
    def unload() -> None:
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            return
