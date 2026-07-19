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
