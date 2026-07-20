"""Repetition kill: pickers skip recently-used material (spec 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.weird_stories import pick_weird, WEIRD_CAPSULES
from src.content.debate_topics import pick_debate, DEBATE_TOPICS


def test_excluded_key_skipped():
    base = pick_weird(0)
    nxt = pick_weird(0, exclude={base["key"]})
    assert nxt["key"] != base["key"]


def test_deterministic_with_same_exclude():
    ex = {WEIRD_CAPSULES[0]["key"], WEIRD_CAPSULES[1]["key"]}
    assert pick_weird(4, exclude=ex)["key"] == pick_weird(4, exclude=ex)["key"]


def test_all_excluded_still_returns():
    ex = {c["key"] for c in WEIRD_CAPSULES}
    assert pick_weird(0, exclude=ex) is not None


def test_debate_topics_keyed_and_excludable():
    keys = [t["key"] for t in DEBATE_TOPICS]
    assert len(keys) == len(set(keys)) and all(keys)
    base = pick_debate(2)
    assert pick_debate(2, exclude={base["key"]})["key"] != base["key"]
