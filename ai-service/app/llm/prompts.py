from pathlib import Path
from typing import Dict


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def render_review_prompt(context: Dict[str, object]) -> str:
    template = load_prompt("review_risk_analysis_zh.md")
    values = {key: str(value) for key, value in context.items()}
    return template.format_map(values)


def render_rag_review_prompt(context: Dict[str, object]) -> str:
    template = load_prompt("review_risk_analysis_rag_zh.md")
    values = {key: str(value) for key, value in context.items()}
    return template.format_map(values)


def render_repair_prompt(raw_output: str, validation_error: str) -> str:
    template = load_prompt("json_repair_zh.md")
    return template.format(raw_output=raw_output, validation_error=validation_error)
