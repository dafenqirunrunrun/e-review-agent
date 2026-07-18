from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPT_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"VLM_PROMPT_NOT_AVAILABLE:{name}")
    return path.read_text(encoding="utf-8")
