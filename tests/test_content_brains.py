"""Phase A: debate topics, weird stories, safety guards, story writer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.debate_topics import DEBATE_TOPICS, pick_debate
from src.content.weird_stories import WEIRD_CAPSULES, WEIRD_HYPOTHETICALS, pick_weird
from src.content.safety_guards import mentions_named_person
from src.content.trend_sources import is_unsafe
from studio.story_writer import validate_story, write_story, STORY_SCHEMA


def test_debate_pool_size_and_safety():
    assert len(DEBATE_TOPICS) >= 35
    for t in DEBATE_TOPICS:
        assert t["topic"] and t["stance_seed"] and t["binary_cta"]
        joined = " ".join(t.values())
        assert not is_unsafe(joined), f"unsafe debate topic: {t['topic']}"
        assert not mentions_named_person(joined), f"named person in: {t['topic']}"


def test_pick_debate_deterministic():
    assert pick_debate(3) == pick_debate(3)
    assert pick_debate(None) == DEBATE_TOPICS[0]


def test_weird_capsules_schema_and_safety():
    assert len(WEIRD_CAPSULES) >= 15
    assert len(WEIRD_HYPOTHETICALS) >= 5
    for c in WEIRD_CAPSULES:
        for k in ("hook_fact", "escalation", "source_note", "lesson_theme", "send_cta"):
            assert c.get(k), f"capsule missing {k}"
        assert c["source_note"] != "hypothetical"
        assert "send this" in c["send_cta"].lower()
    for h in WEIRD_HYPOTHETICALS:
        assert h.get("hypothetical") is True
        assert h["source_note"] == "hypothetical"


def test_weird_rotation_mixes_pools():
    picks = [pick_weird(i) for i in range(12)]
    assert any(p.get("hypothetical") for p in picks)
    assert any(not p.get("hypothetical") for p in picks)
    assert pick_weird(5) == pick_weird(5)


def test_named_person_guard_blocks_modern_blames():
    assert mentions_named_person("Everyone defends Taylor Swift like a religion.")
    assert mentions_named_person("Dr. Somebody said you should wake at 4am.")
    assert mentions_named_person("The takes about Jordan Peterson miss the point.")


def test_named_person_guard_allows_ancients_and_sentences():
    assert not mentions_named_person("Diogenes told Alexander to move out of his sunlight.")
    assert not mentions_named_person("Marcus Aurelius wrote his journal at dawn.")
    assert not mentions_named_person("Send this to your most stubborn friend.")
    assert not mentions_named_person("Imagine Suppose This That capitalized sentence leads.")


def test_validate_story_limits():
    long_reframe = 'Seneca was one of the richest men in Rome. Marble halls, hundreds of servants, senators begging for his time. And once a month he walked away from all of it. He put on the roughest cloak he owned. He slept on the bare floor. He ate stale bread and drank only water, for days at a time, on purpose. His friends thought he had lost his mind. He said he was rehearsing. Rehearsing the exact thing he was most afraid of, so the fear could never blackmail him again. When exile finally came for him, and it did come, he walked out of Rome calm, because he had already lived his nightmare a hundred times and knew he could survive it. The man who practiced losing everything became the one man in Rome who could not be robbed.'
    good = {"beat_hook": "This man lived in a barrel and won.",
            "beat_reframe": long_reframe,
            "quote_row": 3, "beat_cta": "Send this to your freest friend.",
            "topic_query": "ancient ruins", "caption_first_line": "He chose the barrel."}
    ok, r = validate_story(good)
    assert ok, r
    bad_q = dict(good, beat_hook="Why would anyone live in a barrel though?")
    assert validate_story(bad_q)[0] is False           # question hook rejected
    bad_len = dict(good, beat_hook=" ".join(["word"] * 16))
    assert validate_story(bad_len)[0] is False
    too_short = dict(good, beat_reframe="He owned nothing and feared no one alive.")
    ok, r = validate_story(too_short)
    assert ok is False and "60s story" in r            # <1-min stories rejected
    too_long = dict(good, beat_reframe=" ".join(["word"] * 250))
    assert validate_story(too_long)[0] is False


def test_write_story_uses_client_and_validates():
    class FakeClient:
        def call(self, role, prefix, role_system, user, schema):
            assert role == "story_writer"
            assert schema == STORY_SCHEMA
            return {"beat_hook": "A rich man rehearsed being poor.",
                    "beat_reframe": 'Seneca was one of the richest men in Rome. Marble halls, hundreds of servants, senators begging for his time. And once a month he walked away from all of it. He put on the roughest cloak he owned. He slept on the bare floor. He ate stale bread and drank only water, for days at a time, on purpose. His friends thought he had lost his mind. He said he was rehearsing. Rehearsing the exact thing he was most afraid of, so the fear could never blackmail him again. When exile finally came for him, and it did come, he walked out of Rome calm, because he had already lived his nightmare a hundred times and knew he could survive it. The man who practiced losing everything became the one man in Rome who could not be robbed.',
                    "quote_row": 7, "beat_cta": "Send this to a friend ruled by fear.",
                    "topic_query": "roman villa", "caption_first_line": "He practiced losing everything.",
                    "trend_tag": "stoicism"}
    out = write_story(FakeClient(), "weird", {"hook_fact": "x"}, [{"row_number": 7, "quote": "q"}])
    assert out and out["quote_row"] == 7


def test_write_story_none_on_invalid():
    class BadClient:
        def call(self, *a, **k):
            return {"beat_hook": "Why?", "beat_reframe": "r", "quote_row": 1,
                    "beat_cta": "c", "topic_query": "t", "caption_first_line": "f"}
    assert write_story(BadClient(), "debate", {}, []) is None
