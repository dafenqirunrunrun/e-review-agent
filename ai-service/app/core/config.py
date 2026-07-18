import os

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "E-Review Agent AI Service"
    api_prefix: str = "/api/v1"
    default_port: int = 8008
    cases_path: str = "data/review_cases.json"
    agent_framework_provider: str = "langgraph"

    @property
    def agent_framework_enabled(self) -> bool:
        return _env_bool("AGENT_FRAMEWORK_ENABLED", False)

    @property
    def agent_framework_fallback_enabled(self) -> bool:
        return _env_bool("AGENT_FRAMEWORK_FALLBACK_ENABLED", True)

    @property
    def agent_framework_require_api_key(self) -> bool:
        return _env_bool("AGENT_FRAMEWORK_REQUIRE_API_KEY", False)

    @property
    def openai_api_key_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


settings = Settings()
