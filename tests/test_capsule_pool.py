"""60-capsule pool: keyed, attested, safe (spec 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.weird_stories import WEIRD_CAPSULES, WEIRD_HYPOTHETICALS
from src.content.trend_sources import is_unsafe
from src.content.safety_guards import mentions_named_person


def test_pool_size():
    assert len(WEIRD_CAPSULES) >= 54
    assert len(WEIRD_CAPSULES) + len(WEIRD_HYPOTHETICALS) >= 60


def test_every_capsule_keyed_and_complete():
    seen = set()
    for c in WEIRD_CAPSULES + WEIRD_HYPOTHETICALS:
        assert c.get("key") and c["key"] not in seen, c.get("key")
        seen.add(c["key"])
    for c in WEIRD_CAPSULES:
        for f in ("hook_fact", "escalation", "source_note", "lesson_theme", "send_cta"):
            assert c.get(f), (c["key"], f)
        assert "Send this" in c["send_cta"], c["key"]


def test_every_capsule_safe():
    for c in WEIRD_CAPSULES:
        joined = " ".join([c["hook_fact"], c["escalation"], c["send_cta"]])
        assert not is_unsafe(joined), c["key"]
        assert not mentions_named_person(joined), c["key"]
