from __future__ import annotations

import gc
import importlib.util
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.runtime.gpu_gate import gpu_exclusive_gate


@dataclass(frozen=True)
class Qwen3VlRuntimeRequest:
    image_paths: list[str]
    prompt: str
    model_dir: Path
    max_new_tokens: int = 48
    max_pixels: int = 147_456
    min_pixels: int = 65_536
    do_sample: bool = False
    stage: str = "qwen3-vl-runtime"
    unload_after_request: bool = True
    min_free_memory_mb: int = 5200
    check_interval_seconds: int = 30
    stable_checks: int = 3
    timeout_seconds: int = 14_400
    device_placement: str = "auto"


@dataclass(frozen=True)
class Qwen3VlRuntimeResult:
    raw_text: str = ""
    real_inference: bool = False
    cuda_used: bool = False
    fallback_used: bool = False
    generate_executed: bool = False
    model_name: str = "Qwen/Qwen3-VL-2B-Instruct"
    provider_name: str = "local_qwen3_vl_transformers"
    input_token_count: int = 0
    output_token_count: int = 0
    model_load_ms: float | None = None
    processor_load_ms: float | None = None
    inference_ms: float | None = None
    total_latency_ms: float | None = None
    gpu_memory_before_load_mb: float | None = None
    gpu_memory_after_load_mb: float | None = None
    gpu_peak_memory_mb: float | None = None
    gpu_memory_after_unload_mb: float | None = None
    unload_completed: bool = False
    device_map_used: bool = False
    manual_to_cuda_used: bool = False
    accelerate_available: bool = False
    gpu_memory_budget_mb: int | None = None
    stable_free_memory_mb: int | None = None
    local_files_only: bool = True
    batch_size: int = 1
    max_new_tokens: int = 48
    do_sample: bool = False
    image_size: list[int] | None = None
    dtype: str = "torch.bfloat16"
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    runtime_counters: dict[str, int] = field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None


class Qwen3VlRuntimeCounters:
    runtime_instance_count = 0
    processor_load_count = 0
    model_load_count = 0
    generate_call_count = 0
    unload_count = 0
    gpu_lock_acquire_count = 0

    @classmethod
    def snapshot(cls) -> dict[str, int]:
        return {
            "runtime_instance_count": cls.runtime_instance_count,
            "processor_load_count": cls.processor_load_count,
            "model_load_count": cls.model_load_count,
            "generate_call_count": cls.generate_call_count,
            "unload_count": cls.unload_count,
            "gpu_lock_acquire_count": cls.gpu_lock_acquire_count,
        }

    @classmethod
    def reset(cls) -> None:
        cls.runtime_instance_count = 0
        cls.processor_load_count = 0
        cls.model_load_count = 0
        cls.generate_call_count = 0
        cls.unload_count = 0
        cls.gpu_lock_acquire_count = 0


class Qwen3VlRuntimeSession:
    def __init__(
        self,
        model_dir: Path,
        stage: str = "qwen3-vl-runtime-session",
        min_free_memory_mb: int = 5200,
        check_interval_seconds: int = 30,
        stable_checks: int = 3,
        timeout_seconds: int = 14_400,
        device_placement: str = "auto",
    ):
        Qwen3VlRuntimeCounters.runtime_instance_count += 1
        self.model_dir = model_dir
        self.stage = stage
        self.min_free_memory_mb = min_free_memory_mb
        self.check_interval_seconds = check_interval_seconds
        self.stable_checks = stable_checks
        self.timeout_seconds = timeout_seconds
        self.device_placement = device_placement
        self.model = None
        self.processor = None
        self.torch = None
        self.dtype = None
        self.gate_status = None
        self.gate_context = None
        self.gpu_memory_budget_mb = None
        self.processor_load_ms = None
        self.model_load_ms = None
        self.gpu_wait_ms = None
        self.gpu_lock_acquire_ms = None
        self.gpu_memory_before_load_mb = None
        self.gpu_memory_after_load_mb = None
        self.gpu_memory_after_unload_mb = None
        self.unload_completed = False
        self.session_started = None

    def __enter__(self) -> Qwen3VlRuntimeSession:
        started = time.perf_counter()
        if not self.model_dir.exists() or not (self.model_dir / "config.json").exists():
            raise RuntimeError("VLM_MODEL_NOT_READY")
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA_UNAVAILABLE")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("BFLOAT16_UNSUPPORTED")
        self.torch = torch
        self.dtype = torch.bfloat16
        torch.cuda.reset_peak_memory_stats()
        self.gpu_memory_before_load_mb = _cuda_reserved_mb(torch)

        gate_started = time.perf_counter()
        self.gate_context = gpu_exclusive_gate(
            stage=self.stage,
            min_free_memory_mb=self.min_free_memory_mb,
            check_interval_seconds=self.check_interval_seconds,
            stable_checks=self.stable_checks,
            timeout_seconds=self.timeout_seconds,
        )
        self.gate_status = self.gate_context.__enter__()
        self.gpu_wait_ms = _elapsed_ms(gate_started)
        self.gpu_lock_acquire_ms = self.gpu_wait_ms
        Qwen3VlRuntimeCounters.gpu_lock_acquire_count += 1

        processor_started = time.perf_counter()
        self.processor = AutoProcessor.from_pretrained(str(self.model_dir), local_files_only=True)
        self.processor_load_ms = _elapsed_ms(processor_started)
        Qwen3VlRuntimeCounters.processor_load_count += 1

        model_started = time.perf_counter()
        load_kwargs: dict[str, Any] = {"torch_dtype": self.dtype, "local_files_only": True}
        accelerate_available = self.accelerate_available
        if self.device_placement == "auto" and accelerate_available:
            stable_free = self.gate_status.memory_free_mb or self.min_free_memory_mb
            self.gpu_memory_budget_mb = max(1024, stable_free - 400)
            load_kwargs["device_map"] = "auto"
            load_kwargs["max_memory"] = {0: f"{self.gpu_memory_budget_mb}MiB", "cpu": "24GiB"}
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(str(self.model_dir), **load_kwargs)
        if self.device_placement == "cuda" or not self.device_map_used:
            self.model = self.model.to("cuda")
        self.model.eval()
        self.model_load_ms = _elapsed_ms(model_started)
        self.gpu_memory_after_load_mb = _cuda_reserved_mb(torch)
        Qwen3VlRuntimeCounters.model_load_count += 1
        self.session_started = started
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        unload_started = time.perf_counter()
        try:
            del self.model
            del self.processor
        except Exception:
            pass
        gc.collect()
        if self.torch is not None and self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()
            try:
                self.torch.cuda.ipc_collect()
            except Exception:
                pass
            self.gpu_memory_after_unload_mb = _cuda_reserved_mb(self.torch)
        self.unload_completed = True
        Qwen3VlRuntimeCounters.unload_count += 1
        self.model_unload_ms = _elapsed_ms(unload_started)
        if self.gate_context is not None:
            self.gate_context.__exit__(exc_type, exc, traceback)

    @property
    def accelerate_available(self) -> bool:
        return importlib.util.find_spec("accelerate") is not None

    @property
    def device_map_used(self) -> bool:
        return self.device_placement == "auto" and self.accelerate_available

    def generate(
        self,
        image_paths: list[str],
        prompt: str,
        max_new_tokens: int = 48,
        do_sample: bool = False,
    ) -> Qwen3VlRuntimeResult:
        started_total = time.perf_counter()
        inputs = None
        generated_ids = None
        try:
            if not image_paths:
                return self._blocked("VLM_IMAGE_MISSING", started_total)
            image = Path(image_paths[0])
            if not image.exists():
                return self._blocked("VLM_IMAGE_MISSING", started_total)

            from PIL import Image

            decode_started = time.perf_counter()
            pil_image = Image.open(image).convert("RGB")
            image_decode_ms = _elapsed_ms(decode_started)

            resize_started = time.perf_counter()
            pil_image = _resize_longest_edge(pil_image, max_edge=384)
            image_resize_ms = _elapsed_ms(resize_started)

            prompt_started = time.perf_counter()
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": pil_image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            prompt_build_ms = _elapsed_ms(prompt_started)

            encode_started = time.perf_counter()
            target_device = self.model.device if hasattr(self.model, "device") else self.torch.device("cuda")
            encoded = self.processor(text=[text], images=[pil_image], return_tensors="pt")
            processor_encode_ms = _elapsed_ms(encode_started)

            transfer_started = time.perf_counter()
            inputs = encoded.to(target_device)
            input_transfer_ms = _elapsed_ms(transfer_started)

            generate_started = time.perf_counter()
            with self.torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=do_sample,
                )
            generate_ms = _elapsed_ms(generate_started)
            Qwen3VlRuntimeCounters.generate_call_count += 1

            decode_started = time.perf_counter()
            output_ids = generated_ids[:, inputs.input_ids.shape[1] :]
            raw_text = self.processor.batch_decode(
                output_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]
            decode_ms = _elapsed_ms(decode_started)

            latency_breakdown = {
                "gpu_wait_ms": self.gpu_wait_ms or 0,
                "gpu_lock_acquire_ms": self.gpu_lock_acquire_ms or 0,
                "processor_load_ms": self.processor_load_ms or 0,
                "model_load_ms": self.model_load_ms or 0,
                "image_decode_ms": image_decode_ms,
                "image_resize_ms": image_resize_ms,
                "prompt_build_ms": prompt_build_ms,
                "processor_encode_ms": processor_encode_ms,
                "input_transfer_ms": input_transfer_ms,
                "generate_ms": generate_ms,
                "decode_ms": decode_ms,
                "raw_json_parse_ms": 0,
                "schema_repair_ms": 0,
                "provider_mapping_ms": 0,
                "tool_log_persist_ms": 0,
                "model_unload_ms": 0,
                "gpu_release_wait_ms": 0,
                "total_request_ms": _elapsed_ms(started_total),
            }
            return Qwen3VlRuntimeResult(
                raw_text=raw_text,
                real_inference=bool(raw_text.strip()),
                cuda_used=True,
                fallback_used=False,
                generate_executed=True,
                input_token_count=int(inputs.input_ids.shape[1]),
                output_token_count=int(output_ids.shape[1]),
                processor_load_ms=self.processor_load_ms,
                model_load_ms=self.model_load_ms,
                inference_ms=generate_ms,
                total_latency_ms=latency_breakdown["total_request_ms"],
                gpu_memory_before_load_mb=self.gpu_memory_before_load_mb,
                gpu_memory_after_load_mb=self.gpu_memory_after_load_mb,
                gpu_peak_memory_mb=round(self.torch.cuda.max_memory_reserved(0) / 1024 / 1024, 2),
                gpu_memory_after_unload_mb=self.gpu_memory_after_unload_mb,
                unload_completed=self.unload_completed,
                device_map_used=self.device_map_used,
                manual_to_cuda_used=not self.device_map_used,
                accelerate_available=self.accelerate_available,
                gpu_memory_budget_mb=self.gpu_memory_budget_mb,
                stable_free_memory_mb=self.gate_status.memory_free_mb if self.gate_status else None,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                image_size=list(pil_image.size),
                dtype=str(self.dtype),
                latency_breakdown=latency_breakdown,
                runtime_counters=Qwen3VlRuntimeCounters.snapshot(),
            )
        except self.torch.cuda.OutOfMemoryError as exc:
            return self._blocked("CUDA_OUT_OF_MEMORY", started_total, exc, cuda_used=True)
        except Exception as exc:
            return self._blocked(type(exc).__name__, started_total, exc, cuda_used=True)
        finally:
            try:
                del inputs
                del generated_ids
            except Exception:
                pass
            gc.collect()

    @staticmethod
    def _blocked(
        code: str,
        started_total: float,
        exc: Exception | None = None,
        cuda_used: bool = False,
    ) -> Qwen3VlRuntimeResult:
        return Qwen3VlRuntimeResult(
            cuda_used=cuda_used,
            total_latency_ms=_elapsed_ms(started_total),
            error_code=code,
            error_summary=None if exc is None else str(exc)[:1000],
            runtime_counters=Qwen3VlRuntimeCounters.snapshot(),
        )


class Qwen3VlRuntime:
    def run(self, request: Qwen3VlRuntimeRequest) -> Qwen3VlRuntimeResult:
        started_total = time.perf_counter()
        try:
            with Qwen3VlRuntimeSession(
                model_dir=request.model_dir,
                stage=request.stage,
                min_free_memory_mb=request.min_free_memory_mb,
                check_interval_seconds=request.check_interval_seconds,
                stable_checks=request.stable_checks,
                timeout_seconds=request.timeout_seconds,
                device_placement=request.device_placement,
            ) as session:
                result = session.generate(
                    image_paths=request.image_paths,
                    prompt=request.prompt,
                    max_new_tokens=request.max_new_tokens,
                    do_sample=request.do_sample,
                )
                breakdown = dict(result.latency_breakdown)
                breakdown["model_unload_ms"] = getattr(session, "model_unload_ms", 0)
                breakdown["total_request_ms"] = _elapsed_ms(started_total)
                return Qwen3VlRuntimeResult(
                    **{
                        **result.__dict__,
                        "total_latency_ms": breakdown["total_request_ms"],
                        "gpu_memory_after_unload_mb": session.gpu_memory_after_unload_mb,
                        "unload_completed": session.unload_completed,
                        "latency_breakdown": breakdown,
                        "runtime_counters": Qwen3VlRuntimeCounters.snapshot(),
                    }
                )
        except RuntimeError as exc:
            return Qwen3VlRuntimeSession._blocked(str(exc), started_total, exc)
        except TimeoutError as exc:
            return Qwen3VlRuntimeSession._blocked("GPU_WAIT_TIMEOUT", started_total, exc)


def _cuda_reserved_mb(torch):
    if not torch.cuda.is_available():
        return None
    return round(torch.cuda.memory_reserved(0) / 1024 / 1024, 2)


def _resize_longest_edge(image, max_edge: int = 384):
    width, height = image.size
    longest = max(width, height)
    if longest <= max_edge:
        return image
    scale = max_edge / float(longest)
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(size)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)
