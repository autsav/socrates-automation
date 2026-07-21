"""Conditional revision: subscore report in, never-worse out (spec 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.story_writer import write_story, REVISION_THRESHOLD

POOL = [{"row_number": 1, "quote": "He who has a why can bear any how."}]

_REFRAME = ("You tell yourself tomorrow. " + "He kept walking. " * 24
            + "And nobody expected what he did next. "
            + "He kept going anyway. " * 15)

# Weak hook (all-abstraction, no concrete image) + weak-tier cta ("send" but
# not the specific "send this to the <friend-type>" pattern) -> hook and
# total both score under REVISION_THRESHOLD, firing the revision pass.
WEAK = {"beat_hook": "Your mindset shapes your success and growth every day.",
        "beat_reframe": _REFRAME,
        "quote_row": 1, "beat_cta": "Send this if it hit home.",
        "topic_query": "man storm", "caption_first_line": "Read it again."}

STRONG_REVISION = dict(WEAK,
    beat_hook="You checked your bank app 9 times before lunch today.",
    beat_cta="Send this to the friend who counts everything twice.")


def test_revision_fires_and_ships_better(monkeypatch):
    calls = []

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            if len(calls) <= 2:
                return dict(WEAK)
            return dict(STRONG_REVISION)

    out = write_story(C(), "weird", {"hook_fact": "x"}, POOL)
    assert out is not None and out["beat_hook"].startswith("You checked")
    assert len(calls) == 3                       # 2 drafts + 1 revision
    assert "fixing EXACTLY" in calls[2] or "weakness" in calls[2].lower()


def test_revision_never_worse(monkeypatch):
    calls = []
    WORSE = dict(WEAK, beat_cta="Share.")        # drops out of the "send" tier entirely

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            return dict(WEAK) if len(calls) <= 2 else dict(WORSE)

    out = write_story(C(), "weird", {"hook_fact": "x"}, POOL)
    assert out is not None and out["beat_cta"] == "Send this if it hit home."  # original kept


def test_strong_draft_skips_revision(monkeypatch):
    calls = []
    STRONG = dict(WEAK,
        beat_hook="You counted your savings 3 times on a marble-cold night.",
        beat_cta="Send this to the friend who guards their stuff.")

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            return dict(STRONG)

    out = write_story(C(), "weird", {"hook_fact": "x"}, POOL)
    assert out is not None and len(calls) == 2   # no revision call


def test_punch_mode_skips_revision():
    """Punch mode should never trigger revision, even with low scores."""
    calls = []

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            return {"beat_hook": "Nobody is coming to rescue you from that worn couch tonight now.",
                    "beat_reframe": "",
                    "quote_row": 1,
                    "beat_cta": "Send this to the friend still waiting for a sign to start living.",
                    "topic_query": "man rooftop night", "caption_first_line": "Read it twice."}

    out = write_story(C(), "punch", {"topic": "procrastination"},
                      [{"row_number": 1, "quote": "He who has a why can bear any how."}])
    assert out is not None
    assert len(calls) == 2   # 2 drafts, NO revision call
