"""Declares which prompts the optimizer manages, and exposes their current
champion text (seeding the hardcoded default as v1 on first access)."""
from src.optimizer import prompt_store, registry
import studio.strategist as strategist
import studio.copywriter as copywriter
import studio.trend_scout as trend_scout

MANAGED_PROMPTS = [
    {"key": "prompt.strategist.role", "default": strategist._ROLE_DEFAULT},
    {"key": "prompt.strategist.prefix", "default": strategist._PREFIX_DEFAULT},
    {"key": "prompt.copywriter.draft", "default": copywriter._DRAFT_ROLE},
    {"key": "prompt.copywriter.revise", "default": copywriter._REVISE_ROLE},
    {"key": "prompt.trend_scout.role", "default": trend_scout._ROLE},
]


def iter_managed(db_path=registry.DB_PATH):
    out = []
    for m in MANAGED_PROMPTS:
        text = prompt_store.get(m["key"], m["default"], db_path)
        out.append({"key": m["key"], "champion_text": text})
    return out
