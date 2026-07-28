import pytest

from studio.social_strategist import (
    _validate, _linter, _build_user_msg, StrategyValidationError,
)


VALID_CREATIVE = {
    "hook": "You will not finish this.",
    "bridge": None,
    "quote": "We suffer more in imagination than in reality.",
    "cta": "Save this for the next spiral.",
    "caption": "Seneca hits different at 2am.",
    "hashtags": ["#stoicism", "#philosophy", "#seneca"],
    "mood": "stark",
    "attribution": "Seneca",
    "audience": "doomscrollers",
    "row_number": 42,
}


def test_validate_accepts_good_creative():
    _validate(VALID_CREATIVE)  # no raise


def test_validate_rejects_long_hook():
    bad = {**VALID_CREATIVE, "hook": "this is a really really long hook that goes on forever and ever and ever"}
    with pytest.raises(StrategyValidationError, match="hook"):
        _validate(bad)


def test_validate_rejects_too_few_hashtags():
    bad = {**VALID_CREATIVE, "hashtags": ["#stoicism"]}
    with pytest.raises(StrategyValidationError, match="hashtag"):
        _validate(bad)


def test_validate_rejects_too_many_hashtags():
    bad = {**VALID_CREATIVE, "hashtags": ["#a", "#b", "#c", "#d", "#e", "#f"]}
    with pytest.raises(StrategyValidationError, match="hashtag"):
        _validate(bad)


def test_linter_rejects_engagement_bait():
    for phrase in ["like if you agree", "comment below", "share if you",
                   "smash that like", "double tap", "follow for more"]:
        with pytest.raises(StrategyValidationError, match="engagement-bait"):
            _linter(f"This caption contains {phrase} somewhere.")


def test_linter_accepts_clean_caption():
    _linter("Save this for the next time you spiral at 2am.")  # no raise


def test_build_user_msg_contains_all_inputs():
    trend = {"headline": "Marcus Aurelius on doomscrolling",
             "keywords": ["marcus aurelius", "doomscrolling", "stark"],
             "angle": "Stoic response to late-night scrolling"}
    quote_row = {"text": "The happiness of your life depends on the quality of your thoughts.",
                 "attribution": "Marcus Aurelius", "row_number": 17, "mood": "stark"}
    msg = _build_user_msg(trend, quote_row, "doomscrollers")
    assert "Marcus Aurelius on doomscrolling" in msg
    assert "marcus aurelius" in msg
    assert "happiness of your life" in msg
    assert "Marcus Aurelius" in msg
    assert "doomscrollers" in msg