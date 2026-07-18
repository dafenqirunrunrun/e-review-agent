import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class VlmConfig:
    provider: str = os.getenv("E_REVIEW_VLM_PROVIDER", "local_qwen3_vl_transformers")
    model_dir: Path = Path(os.getenv("E_REVIEW_VLM_MODEL_DIR", "./models/Qwen3-VL-2B-Instruct"))
    device: str = os.getenv("E_REVIEW_VLM_DEVICE", "cuda")
    dtype: str = os.getenv("E_REVIEW_VLM_DTYPE", "auto")
    load_in_4bit: bool = _env_bool("E_REVIEW_VLM_LOAD_IN_4BIT", False)
    max_new_tokens: int = _env_int("E_REVIEW_VLM_MAX_NEW_TOKENS", 384)
    max_images: int = _env_int("E_REVIEW_VLM_MAX_IMAGES", 4)
    max_pixels: int = _env_int("E_REVIEW_VLM_MAX_PIXELS", 1_048_576)
    min_pixels: int = _env_int("E_REVIEW_VLM_MIN_PIXELS", 65_536)
    timeout_seconds: int = _env_int("E_REVIEW_VLM_TIMEOUT_SECONDS", 180)
    enable_thinking: bool = _env_bool("E_REVIEW_VLM_ENABLE_THINKING", False)
    lazy_load: bool = _env_bool("E_REVIEW_VLM_LAZY_LOAD", True)
    unload_after_request: bool = _env_bool("E_REVIEW_VLM_UNLOAD_AFTER_REQUEST", True)
    memory_strategy: str = os.getenv("E_REVIEW_VLM_MEMORY_STRATEGY", "serial_lazy_load")
    max_concurrency: int = _env_int("E_REVIEW_VLM_MAX_CONCURRENCY", 1)
    queue_timeout_seconds: int = _env_int("E_REVIEW_VLM_QUEUE_TIMEOUT_SECONDS", 600)
    session_idle_timeout_seconds: int = _env_int("E_REVIEW_VLM_SESSION_IDLE_TIMEOUT_SECONDS", 60)


def load_config() -> VlmConfig:
    return VlmConfig()
