"""Declares which prompts the optimizer manages, and exposes their current
champion text (seeding the hardcoded default as v1 on first access)."""
from src.optimizer import prompt_store, registry
import studio.strategist as strategist
import studio.copywriter as copywriter
import studio.trend_scout as trend_scout
import studio.music_director as music_director
import studio.story_writer as story_writer
import src.content.controversy_engine as controversy_engine

MANAGED_PROMPTS = [
    {"key": "prompt.strategist.role", "default": strategist._ROLE_DEFAULT},
    {"key": "prompt.strategist.prefix", "default": strategist._PREFIX_DEFAULT},
    {"key": "prompt.copywriter.draft", "default": copywriter._DRAFT_ROLE_DEFAULT},
    {"key": "prompt.copywriter.revise", "default": copywriter._REVISE_ROLE_DEFAULT},
    {"key": "prompt.trend_scout.role", "default": trend_scout._ROLE_DEFAULT},
    {"key": "prompt.music_director.query", "default": music_director._QUERY_ROLE_DEFAULT},
    {"key": "prompt.music_director.rank", "default": music_director._RANK_ROLE_DEFAULT},
    {"key": "prompt.story_writer.role", "default": story_writer._ROLE_DEFAULT},
    # The Controversy Engine (ROAST/VERDICT/DEBATE) is the highest-volume
    # generator and was previously hardcoded — routing it through prompt_store
    # lets the optimizer A/B its system prompt against real sends-per-reach.
    {"key": "prompt.controversy.system", "default": controversy_engine._SYSTEM_PROMPT},
]


def iter_managed(db_path=registry.DB_PATH):
    out = []
    for m in MANAGED_PROMPTS:
        text = prompt_store.get(m["key"], m["default"], db_path)
        out.append({"key": m["key"], "champion_text": text})
    return out
