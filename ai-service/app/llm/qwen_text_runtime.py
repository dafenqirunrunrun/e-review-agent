from __future__ import annotations

import gc
import importlib.util
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.llm.schemas import ReviewRiskAnalysis
from app.runtime.gpu_gate import gpu_exclusive_gate


@dataclass(frozen=True)
class QwenTextRuntimeRequest:
    review_text: str
    rating: int | None
    product_category: str = "synthetic/private exploratory product"
    max_new_tokens: int = 128
    max_input_tokens: int = 1024
    do_sample: bool = False
    rag_cases: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class QwenTextRuntimeResult:
    sample_id_hash: str
    real_inference: bool = False
    cuda_used: bool = False
    fallback_used: bool = False
    generate_executed: bool = False
    schema_valid: bool = False
    repair_attempted: bool = False
    input_token_count: int = 0
    output_token_count: int = 0
    raw_output_hash: str | None = None
    parsed_risk_type: str | None = None
    parsed_risk_level: str | None = None
    parsed_need_human_review: bool | None = None
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    error_code: str | None = None
    error_summary: str | None = None


class QwenTextRuntimeCounters:
    runtime_instance_count = 0
    tokenizer_load_count = 0
    model_load_count = 0
    generate_call_count = 0
    unload_count = 0
    gpu_lock_acquire_count = 0

    @classmethod
    def snapshot(cls) -> dict[str, int]:
        return {
            "runtime_instance_count": cls.runtime_instance_count,
            "tokenizer_load_count": cls.tokenizer_load_count,
            "model_load_count": cls.model_load_count,
            "generate_call_count": cls.generate_call_count,
            "unload_count": cls.unload_count,
            "gpu_lock_acquire_count": cls.gpu_lock_acquire_count,
        }

    @classmethod
    def reset(cls) -> None:
        cls.runtime_instance_count = 0
        cls.tokenizer_load_count = 0
        cls.model_load_count = 0
        cls.generate_call_count = 0
        cls.unload_count = 0
        cls.gpu_lock_acquire_count = 0


class QwenTextRuntimeSession:
    def __init__(
        self,
        model_dir: Path,
        stage: str = "qwen-text-runtime-session",
        min_free_memory_mb: int = 5200,
        check_interval_seconds: int = 30,
        stable_checks: int = 3,
        timeout_seconds: int = 0,
        device_placement: str = "cuda",
        gpu_gate_mode: str = "auto",
        max_wddm_total_utilization: int = 60,
        max_free_memory_drop_mb: int = 256,
        require_zero_numeric_compute_processes: bool = True,
        allow_wddm_graphics_activity: bool = True,
    ):
        QwenTextRuntimeCounters.runtime_instance_count += 1
        self.model_dir = model_dir
        self.stage = stage
        self.min_free_memory_mb = min_free_memory_mb
        self.check_interval_seconds = check_interval_seconds
        self.stable_checks = stable_checks
        self.timeout_seconds = timeout_seconds
        self.device_placement = device_placement
        self.gpu_gate_mode = gpu_gate_mode
        self.max_wddm_total_utilization = max_wddm_total_utilization
        self.max_free_memory_drop_mb = max_free_memory_drop_mb
        self.require_zero_numeric_compute_processes = require_zero_numeric_compute_processes
        self.allow_wddm_graphics_activity = allow_wddm_graphics_activity
        self.model = None
        self.tokenizer = None
        self.torch = None
        self.dtype = None
        self.gate_context = None
        self.gate_status = None
        self.gpu_wait_ms = 0.0
        self.gpu_lock_acquire_ms = 0.0
        self.tokenizer_load_ms = 0.0
        self.model_load_ms = 0.0
        self.model_unload_ms = 0.0
        self.gpu_memory_before_load_mb = None
        self.gpu_memory_after_load_mb = None
        self.gpu_memory_after_unload_mb = None
        self.unload_completed = False
        self.session_started = None

    def __enter__(self) -> QwenTextRuntimeSession:
        if not self.model_dir.exists() or not (self.model_dir / "config.json").exists():
            raise RuntimeError("QWEN_TEXT_MODEL_NOT_READY")
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer

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
            gpu_gate_mode=self.gpu_gate_mode,
            max_wddm_total_utilization=self.max_wddm_total_utilization,
            max_free_memory_drop_mb=self.max_free_memory_drop_mb,
            require_zero_numeric_compute_processes=self.require_zero_numeric_compute_processes,
            allow_wddm_graphics_activity=self.allow_wddm_graphics_activity,
        )
        self.gate_status = self.gate_context.__enter__()
        self.gpu_wait_ms = _elapsed_ms(gate_started)
        self.gpu_lock_acquire_ms = self.gpu_wait_ms
        QwenTextRuntimeCounters.gpu_lock_acquire_count += 1

        tokenizer_started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
        self.tokenizer_load_ms = _elapsed_ms(tokenizer_started)
        QwenTextRuntimeCounters.tokenizer_load_count += 1

        model_started = time.perf_counter()
        dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
        kwargs: dict[str, Any] = {dtype_key: self.dtype, "local_files_only": True}
        if self.device_placement == "auto" and importlib.util.find_spec("accelerate") is not None:
            kwargs["device_map"] = "auto"
        self.model = AutoModelForCausalLM.from_pretrained(str(self.model_dir), **kwargs)
        if self.device_placement == "cuda" or "device_map" not in kwargs:
            self.model = self.model.to("cuda")
        self.model.eval()
        self.model_load_ms = _elapsed_ms(model_started)
        self.gpu_memory_after_load_mb = _cuda_reserved_mb(torch)
        self.session_started = time.perf_counter()
        QwenTextRuntimeCounters.model_load_count += 1
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        unload_started = time.perf_counter()
        try:
            del self.model
            del self.tokenizer
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
        self.model_unload_ms = _elapsed_ms(unload_started)
        self.unload_completed = True
        QwenTextRuntimeCounters.unload_count += 1
        if self.gate_context is not None:
            self.gate_context.__exit__(exc_type, exc, traceback)

    def generate(self, request: QwenTextRuntimeRequest, sample_id_hash: str) -> QwenTextRuntimeResult:
        started_total = time.perf_counter()
        inputs = None
        generated = None
        try:
            prompt_started = time.perf_counter()
            prompt = _build_prompt(request)
            prompt_build_ms = _elapsed_ms(prompt_started)

            encode_started = time.perf_counter()
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an ecommerce review risk auditor. Output only valid JSON. "
                        "Do not output chain-of-thought, Markdown, refunds, bans, or compensation actions."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            try:
                rendered = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                rendered = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                rendered += "\n/no_think"
            inputs = self.tokenizer([rendered], return_tensors="pt", truncation=True, max_length=request.max_input_tokens)
            tokenizer_encode_ms = _elapsed_ms(encode_started)

            transfer_started = time.perf_counter()
            device = next(self.model.parameters()).device
            inputs = {key: value.to(device) for key, value in inputs.items()}
            input_transfer_ms = _elapsed_ms(transfer_started)
            input_token_count = int(inputs["input_ids"].shape[-1])

            generate_started = time.perf_counter()
            with self.torch.inference_mode():
                generated = self.model.generate(
                    **inputs,
                    max_new_tokens=request.max_new_tokens,
                    do_sample=request.do_sample,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
            prefill_and_generate_ms = _elapsed_ms(generate_started)
            QwenTextRuntimeCounters.generate_call_count += 1

            decode_started = time.perf_counter()
            output_ids = generated[0][input_token_count:]
            raw_text = self.tokenizer.decode(output_ids, skip_special_tokens=True).strip()
            decode_ms = _elapsed_ms(decode_started)

            parse_started = time.perf_counter()
            parsed, parse_error = _parse_review_json(raw_text)
            json_parse_ms = _elapsed_ms(parse_started)
            repair_started = time.perf_counter()
            repair_attempted = parsed is None
            if parsed is None:
                parsed, parse_error = _repair_review_json(parse_error)
            schema_repair_ms = _elapsed_ms(repair_started) if repair_attempted else 0.0

            provider_mapping_started = time.perf_counter()
            provider_mapping_ms = _elapsed_ms(provider_mapping_started)
            latency_breakdown = {
                "gpu_wait_ms": self.gpu_wait_ms,
                "gpu_lock_acquire_ms": self.gpu_lock_acquire_ms,
                "tokenizer_load_ms": self.tokenizer_load_ms,
                "model_load_ms": self.model_load_ms,
                "prompt_build_ms": prompt_build_ms,
                "retrieval_ms": 0.0,
                "tokenizer_encode_ms": tokenizer_encode_ms,
                "input_transfer_ms": input_transfer_ms,
                "prefill_and_generate_ms": prefill_and_generate_ms,
                "decode_ms": decode_ms,
                "json_parse_ms": json_parse_ms,
                "schema_repair_ms": schema_repair_ms,
                "provider_mapping_ms": provider_mapping_ms,
                "model_unload_ms": 0.0,
                "gpu_release_wait_ms": 0.0,
                "active_request_ms": _elapsed_ms(started_total),
            }
            return QwenTextRuntimeResult(
                sample_id_hash=sample_id_hash,
                real_inference=bool(raw_text),
                cuda_used=True,
                fallback_used=False,
                generate_executed=True,
                schema_valid=parsed is not None,
                repair_attempted=repair_attempted,
                input_token_count=input_token_count,
                output_token_count=int(output_ids.shape[-1]),
                raw_output_hash=_sha256_short(raw_text),
                parsed_risk_type=None if parsed is None else parsed.risk_type,
                parsed_risk_level=None if parsed is None else parsed.risk_level,
                parsed_need_human_review=None if parsed is None else parsed.need_human_review,
                latency_breakdown=latency_breakdown,
                error_code=None if parsed is not None else "SCHEMA_INVALID",
                error_summary=parse_error,
            )
        except self.torch.cuda.OutOfMemoryError as exc:
            return self._blocked(sample_id_hash, "CUDA_OUT_OF_MEMORY", started_total, exc, cuda_used=True)
        except Exception as exc:
            return self._blocked(sample_id_hash, type(exc).__name__, started_total, exc, cuda_used=True)
        finally:
            try:
                del inputs
                del generated
            except Exception:
                pass
            gc.collect()

    def _blocked(
        self,
        sample_id_hash: str,
        code: str,
        started_total: float,
        exc: Exception | None = None,
        cuda_used: bool = False,
    ) -> QwenTextRuntimeResult:
        return QwenTextRuntimeResult(
            sample_id_hash=sample_id_hash,
            cuda_used=cuda_used,
            latency_breakdown={"active_request_ms": _elapsed_ms(started_total)},
            error_code=code,
            error_summary=None if exc is None else str(exc)[:1000],
        )


def _build_prompt(request: QwenTextRuntimeRequest) -> str:
    rag_summary = json.dumps(request.rag_cases[:3], ensure_ascii=False)
    return (
        "Analyze the ecommerce review and return exactly one JSON object with keys: "
        "risk_type, risk_level, sentiment, evidence, reason, suggestion, "
        "need_human_review, confidence, missing_information.\n"
        "Allowed risk_type: normal_review, negative_review, after_sales_risk.\n"
        "Allowed risk_level: low, medium, high.\n"
        "Allowed sentiment: positive, neutral, negative.\n"
        "Use uncertain or missing_information when evidence is insufficient.\n"
        "Do not recommend automatic refund, ban, or compensation.\n"
        f"rating: {request.rating if request.rating is not None else 'unknown'}\n"
        f"product_category: {request.product_category}\n"
        f"synthetic_rag_cases: {rag_summary}\n"
        f"review_text: {request.review_text}\n"
    )


def _parse_review_json(raw_text: str) -> tuple[ReviewRiskAnalysis | None, str | None]:
    try:
        text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r"^.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("JSON object not found")
        return ReviewRiskAnalysis.model_validate(json.loads(text[start : end + 1])), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:400]}"


def _repair_review_json(parse_error: str | None) -> tuple[ReviewRiskAnalysis | None, str | None]:
    try:
        return ReviewRiskAnalysis.model_validate(
            {
                "risk_type": "normal_review",
                "risk_level": "low",
                "sentiment": "neutral",
                "evidence": ["model output required schema repair"],
                "reason": "The model output did not contain a parseable JSON object; repaired to a conservative schema-valid result.",
                "suggestion": "Route to human review if this happens on non-canary traffic.",
                "need_human_review": True,
                "confidence": 0.3,
                "missing_information": ["raw model output was not valid JSON"],
            }
        ), parse_error
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:400]}"


def _sha256_short(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:24]


def _cuda_reserved_mb(torch):
    if not torch.cuda.is_available():
        return None
    return round(torch.cuda.memory_reserved(0) / 1024 / 1024, 2)


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)
