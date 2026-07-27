import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import strategist
from studio.types import PerformanceBrief, CreativeBrief


def _perf():
    return PerformanceBrief("2026-06-23T00:00:00", 10, 90, headline="reels win")


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.last = None

    def call(self, role, prefix, role_sys, user, schema):
        self.last = (role, prefix, role_sys, user)
        return self.payload


def _brief_payload():
    return {"audience": "stuck", "topic_theme": "fear", "quote": {"row_number": 3},
            "format": "reel", "angle": "confront", "must_include": [],
            "must_avoid": [], "slot": 0, "hypothesis": "fear hooks land"}


def test_shared_prefix_contains_headline():
    assert "reels win" in strategist.shared_prefix(_perf())


def test_build_prompt_lists_pool():
    pool = [{"row_number": 3, "quote": "Know thyself", "audience": "stuck"}]
    prefix, role = strategist.build_prompt(_perf(), 0, [], pool)
    assert "Know thyself" in role and "content director" in role.lower()


def test_make_brief_returns_creativebrief():
    pool = [{"row_number": 3, "quote": "Know thyself", "audience": "stuck"}]
    c = _FakeClient(_brief_payload())
    b = strategist.make_brief(c, _perf(), 0, [], pool)
    assert isinstance(b, CreativeBrief) and b.audience == "stuck"
    assert c.last[0] == "strategist"
