"""Playbooks are the distilled domain expertise each agent's prompt embeds."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import playbooks


def test_all_playbooks_exist_and_are_substantial():
    for name in ("STORY_CRAFT", "COPY_CRAFT", "TREND_CRAFT",
                 "MUSIC_CRAFT", "STRATEGY_CRAFT"):
        text = getattr(playbooks, name)
        assert isinstance(text, str) and len(text) >= 400, name


def test_story_craft_covers_core_principles():
    t = playbooks.STORY_CRAFT.lower()
    for concept in ("escalat", "concrete", "twist", "send"):
        assert concept in t


def test_agent_defaults_embed_their_playbooks():
    import studio.copywriter as cw
    import studio.trend_scout as ts
    import studio.music_director as md
    import studio.strategist as st
    assert playbooks.COPY_CRAFT in cw._DRAFT_ROLE_DEFAULT
    assert "critique" in cw._DRAFT_ROLE_DEFAULT.lower()
    assert playbooks.TREND_CRAFT in ts._ROLE_DEFAULT
    assert playbooks.MUSIC_CRAFT in md._QUERY_ROLE_DEFAULT
    assert playbooks.STRATEGY_CRAFT in st._ROLE_DEFAULT
