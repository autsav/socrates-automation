"""Loads an agent's markdown system prompt from team/prompts/."""
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text()
