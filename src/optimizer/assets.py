"""Declares which prompts the optimizer manages, and exposes their current
champion text (seeding the hardcoded default as v1 on first access)."""
from src.optimizer import prompt_store, registry
import studio.strategist as strategist
import studio.copywriter as copywriter
import studio.director as director
import studio.trend_scout as trend_scout
import studio.music_director as music_director

MANAGED_PROMPTS = [
    {"key": "prompt.strategist.role", "default": strategist._ROLE_DEFAULT},
    {"key": "prompt.strategist.prefix", "default": strategist._PREFIX_DEFAULT},
    {"key": "prompt.copywriter.draft", "default": copywriter._DRAFT_ROLE_DEFAULT},
    {"key": "prompt.copywriter.revise", "default": copywriter._REVISE_ROLE_DEFAULT},
    {"key": "prompt.director.role", "default": director._ROLE_DEFAULT},
    {"key": "prompt.trend_scout.role", "default": trend_scout._ROLE_DEFAULT},
    {"key": "prompt.music_director.query", "default": music_director._QUERY_ROLE_DEFAULT},
    {"key": "prompt.music_director.rank", "default": music_director._RANK_ROLE_DEFAULT},
]


def iter_managed(db_path=registry.DB_PATH):
    out = []
    for m in MANAGED_PROMPTS:
        text = prompt_store.get(m["key"], m["default"], db_path)
        out.append({"key": m["key"], "champion_text": text})
    return out
