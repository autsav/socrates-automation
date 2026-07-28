import pytest

from studio.social_strategist import (
    StrategyInput, run, StrategyValidationError,
)
from studio.client import StudioError


GOOD_OPUS_RESPONSE = {
    "hook": "You will not finish this video.",
    "bridge": None,
    "quote": "We suffer more in imagination than in reality. — Seneca",
    "cta": "Save this for the next spiral.",
    "caption": "Seneca on late-night overthinking.",
    "hashtags": ["#stoicism", "#seneca", "#philosophy"],
    "mood": "stark",
    "attribution": "Seneca",
    "audience": "doomscrollers",
    "row_number": 42,
}


def test_run_returns_validated_creative(monkeypatch):
    """Happy path: mock client.call returns good dict; run() returns same dict."""
    from studio import social_strategist

    def fake_call(role, prefix, role_system, user, schema):
        assert role == "social_strategist"
        assert prefix  # shared prefix
        assert role_system  # role system
        assert user  # user msg
        return GOOD_OPUS_RESPONSE

    monkeypatch.setattr(social_strategist, "client", type("C", (), {"call": staticmethod(fake_call)})())

    inp = StrategyInput(
        trend={"headline": "Stoic take on doomscrolling",
               "keywords": ["stoicism", "doomscrolling"],
               "angle": "Marcus Aurelius response"},
        quote_row={"text": "We suffer more in imagination than in reality.",
                   "attribution": "Seneca", "row_number": 42, "mood": "stark"},
        audience="doomscrollers",
    )
    out = run(inp)
    assert out["hook"] == GOOD_OPUS_RESPONSE["hook"]
    assert out["hashtags"] == GOOD_OPUS_RESPONSE["hashtags"]


def test_run_rejects_bad_hook_from_opus(monkeypatch):
    """Opus returns hook > 12 words; _validate raises StrategyValidationError."""
    from studio import social_strategist
    bad = {**GOOD_OPUS_RESPONSE,
           "hook": "this is far far too many words for the strict hook limit today"}
    monkeypatch.setattr(social_strategist, "client",
        type("C", (), {"call": staticmethod(lambda *a, **kw: bad)})())
    inp = StrategyInput(
        trend={"headline": "x", "keywords": [], "angle": "y"},
        quote_row={"text": "q", "attribution": "a", "row_number": 1, "mood": "stark"},
        audience="z",
    )
    with pytest.raises(StrategyValidationError, match="hook"):
        run(inp)


def test_run_retries_once_on_studio_error(monkeypatch):
    """First call fails; second succeeds; run() returns creative."""
    from studio import social_strategist
    calls = {"n": 0}

    def flaky_call(role, prefix, role_system, user, schema):
        calls["n"] += 1
        if calls["n"] == 1:
            raise StudioError("opus timeout")
        return GOOD_OPUS_RESPONSE

    monkeypatch.setattr(social_strategist, "client",
        type("C", (), {"call": staticmethod(flaky_call)})())
    inp = StrategyInput(
        trend={"headline": "x", "keywords": [], "angle": "y"},
        quote_row={"text": "q", "attribution": "a", "row_number": 1, "mood": "stark"},
        audience="z",
    )
    out = run(inp)
    assert out["hook"] == GOOD_OPUS_RESPONSE["hook"]
    assert calls["n"] == 2


def test_run_raises_after_two_failures(monkeypatch):
    """Both Opus calls fail; run() propagates StudioError."""
    from studio import social_strategist
    monkeypatch.setattr(social_strategist, "client",
        type("C", (), {"call": staticmethod(lambda *a, **kw: (_ for _ in ()).throw(StudioError("boom")))})())
    inp = StrategyInput(
        trend={"headline": "x", "keywords": [], "angle": "y"},
        quote_row={"text": "q", "attribution": "a", "row_number": 1, "mood": "stark"},
        audience="z",
    )
    with pytest.raises(StudioError):
        run(inp)