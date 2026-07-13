import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import guardrails


def test_ok_when_placeholders_preserved_and_safe():
    champ = "You are the Strategist. Slot {slot}. Pool: {pool}."
    cand = "You are the Content Strategist. Today's slot is {slot}. Choose from {pool}."
    ok, reason = guardrails.validate_prompt_candidate(champ, cand)
    assert ok, reason


def test_fails_when_placeholder_dropped():
    champ = "Slot {slot}. Pool {pool}."
    cand = "Slot {slot}. Pick the best quote."   # dropped {pool}
    ok, reason = guardrails.validate_prompt_candidate(champ, cand)
    assert not ok and "pool" in reason.lower()


def test_fails_when_empty():
    ok, reason = guardrails.validate_prompt_candidate("A {x}", "   ")
    assert not ok


def test_fails_when_candidate_introduces_unsafe(monkeypatch):
    # No-regression: champion is safe, candidate adds unsafe content → reject.
    monkeypatch.setattr(guardrails, "is_unsafe", lambda s: "UNSAFE" in s)
    champ = "You are a safe content agent. Produce good output. Use {x} wisely here."
    cand = "You are a content agent. Produce UNSAFE output. Use {x} wisely here now."
    ok, reason = guardrails.validate_prompt_candidate(champ, cand)
    assert not ok and "unsafe" in reason.lower()


def test_allows_meta_prompt_that_names_unsafe_topics(monkeypatch):
    # A prompt that already trips the denylist (e.g. "reject war/death") is not
    # a regression when the candidate also trips it.
    monkeypatch.setattr(guardrails, "is_unsafe", lambda s: "war" in s)
    champ = "Reject war {x}."
    cand = "Always reject war and violence {x}."
    ok, reason = guardrails.validate_prompt_candidate(champ, cand)
    assert ok, reason
