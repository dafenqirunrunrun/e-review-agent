import importlib.util
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.llm.config import ProviderConfig
from app.llm.providers import ProviderResult


class LocalQwenUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalQwenSettings:
    model_name: str
    model_dir: str
    device: str
    torch_dtype: str
    max_new_tokens: int
    enable_thinking: bool
    timeout_seconds: int

    @property
    def model_source(self) -> str:
        return self.model_dir or self.model_name


def local_qwen_settings() -> LocalQwenSettings:
    return LocalQwenSettings(
        model_name=os.getenv("E_REVIEW_LOCAL_QWEN_MODEL", "Qwen/Qwen3-1.7B"),
        model_dir=os.getenv("E_REVIEW_LOCAL_QWEN_MODEL_DIR", "").strip(),
        device=os.getenv("E_REVIEW_LOCAL_QWEN_DEVICE", "auto").strip().lower(),
        torch_dtype=os.getenv("E_REVIEW_LOCAL_QWEN_TORCH_DTYPE", "auto").strip().lower(),
        max_new_tokens=_env_int("E_REVIEW_LOCAL_QWEN_MAX_NEW_TOKENS", 512),
        enable_thinking=_env_bool("E_REVIEW_LOCAL_QWEN_ENABLE_THINKING", False),
        timeout_seconds=_env_int("E_REVIEW_LOCAL_QWEN_TIMEOUT_SECONDS", 120),
    )


def local_qwen_status(config: Optional[ProviderConfig] = None) -> Dict[str, Any]:
    settings = local_qwen_settings()
    dependency_available = _dependencies_available()
    model_available = _model_source_available(settings)
    state = LocalQwenRuntime.status()
    load_error = state.get("load_error_summary")
    if not dependency_available:
        load_error = "LOCAL_QWEN_DEPENDENCY_NOT_AVAILABLE"
    elif settings.model_dir and not model_available:
        load_error = "LOCAL_QWEN_MODEL_NOT_AVAILABLE"
    return {
        "local_model_available": dependency_available and model_available,
        "local_model_name": settings.model_name,
        "local_model_dir": _safe_path(settings.model_dir),
        "local_model_loaded": bool(state.get("loaded")),
        "local_model_device": state.get("device") or settings.device,
        "local_model_dtype": state.get("dtype") or settings.torch_dtype,
        "enable_thinking": settings.enable_thinking,
        "dependency_available": dependency_available,
        "load_error_summary": load_error,
    }


class LocalQwenRuntime:
    _lock = threading.Lock()
    _tokenizer = None
    _model = None
    _source: Optional[str] = None
    _device: Optional[str] = None
    _dtype: Optional[str] = None
    _load_error_summary: Optional[str] = None

    @classmethod
    def load(cls, settings: LocalQwenSettings):
        source = settings.model_source
        if cls._model is not None and cls._tokenizer is not None and cls._source == source:
            return cls._tokenizer, cls._model
        with cls._lock:
            if cls._model is not None and cls._tokenizer is not None and cls._source == source:
                return cls._tokenizer, cls._model
            try:
                import torch
                import transformers
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                cls._load_error_summary = "LOCAL_QWEN_DEPENDENCY_NOT_AVAILABLE"
                raise LocalQwenUnavailableError(cls._load_error_summary) from exc

            if settings.model_dir and not Path(settings.model_dir).is_dir():
                cls._load_error_summary = "LOCAL_QWEN_MODEL_NOT_AVAILABLE"
                raise LocalQwenUnavailableError(cls._load_error_summary)

            device = settings.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = _resolve_dtype(torch, settings.torch_dtype, device)
            dtype_key = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
            kwargs: Dict[str, Any] = {dtype_key: dtype, "local_files_only": bool(settings.model_dir)}
            use_device_map = settings.device == "auto" and importlib.util.find_spec("accelerate") is not None
            if use_device_map:
                kwargs["device_map"] = "auto"
            try:
                tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=bool(settings.model_dir))
                model = AutoModelForCausalLM.from_pretrained(source, **kwargs)
                if not use_device_map:
                    model = model.to(device)
                model.eval()
            except Exception as exc:
                cls._load_error_summary = _classify_load_error(exc)
                raise LocalQwenUnavailableError(cls._load_error_summary) from exc

            cls._tokenizer = tokenizer
            cls._model = model
            cls._source = source
            cls._device = str(next(model.parameters()).device)
            cls._dtype = str(next(model.parameters()).dtype).replace("torch.", "")
            cls._load_error_summary = None
            return tokenizer, model

    @classmethod
    def status(cls) -> Dict[str, Any]:
        return {
            "loaded": cls._model is not None and cls._tokenizer is not None,
            "device": cls._device,
            "dtype": cls._dtype,
            "load_error_summary": cls._load_error_summary,
        }


class LocalQwenTransformersProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.settings = local_qwen_settings()

    def complete_json(self, prompt: str) -> ProviderResult:
        started = time.perf_counter()
        tokenizer, model = LocalQwenRuntime.load(self.settings)
        messages = [
            {"role": "system", "content": "你是电商评论治理助手。只输出合法 JSON，不输出 Markdown、解释或 <think>。"},
            {"role": "user", "content": prompt},
        ]
        try:
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=self.settings.enable_thinking,
            )
        except TypeError:
            messages[-1]["content"] = prompt + "\n/no_think"
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        inputs = tokenizer([rendered], return_tensors="pt")
        device = next(model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        input_tokens = int(inputs["input_ids"].shape[-1])
        try:
            import torch
            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=self.settings.max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
        except Exception as exc:
            raise LocalQwenUnavailableError(_classify_load_error(exc)) from exc
        output_ids = generated[0][input_tokens:]
        content = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
        return ProviderResult(
            content=content,
            token_usage_input=input_tokens,
            token_usage_output=int(output_ids.shape[-1]),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )


def _dependencies_available() -> bool:
    return importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None


def _model_source_available(settings: LocalQwenSettings) -> bool:
    if settings.model_dir:
        path = Path(settings.model_dir)
        if not path.is_dir() or not (path / "config.json").is_file():
            return False
        single = path / "model.safetensors"
        if single.is_file() and single.stat().st_size > 0:
            return True
        index_path = path / "model.safetensors.index.json"
        if not index_path.is_file():
            return False
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            shards = set((index.get("weight_map") or {}).values())
            return bool(shards) and all((path / shard).is_file() and (path / shard).stat().st_size > 0 for shard in shards)
        except (OSError, ValueError, TypeError):
            return False
    try:
        from huggingface_hub import try_to_load_from_cache
        return try_to_load_from_cache(settings.model_name, "config.json") not in (None, "_CACHED_NO_EXIST")
    except Exception:
        return False


def _resolve_dtype(torch, value: str, device: str):
    if value == "auto":
        return "auto"
    mapping = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    return mapping.get(value, torch.float16 if device == "cuda" else torch.float32)


def _classify_load_error(exc: Exception) -> str:
    text = str(exc).lower()
    name = type(exc).__name__
    if "out of memory" in text or "cuda" in text and "memory" in text:
        return "LOCAL_QWEN_CUDA_OOM"
    if "no such file" in text or "not found" in text or "incorrect path" in text:
        return "LOCAL_QWEN_MODEL_NOT_AVAILABLE"
    return f"LOCAL_QWEN_LOAD_FAILED:{name}"[:160]


def _safe_path(value: str) -> Optional[str]:
    if not value:
        return None
    home = str(Path.home())
    return value.replace(home, "<USER_HOME>")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default
