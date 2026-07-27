"""Tests for Hopecore mood routing in PromptArchitect."""
from src.prompts import architect

HOPEFUL_MOODS = ("cinematic_hopeful", "mystical_greek", "calm_stoic")


def test_hopeful_moods_get_hopecore():
    pa = architect.PromptArchitect()
    for mood in HOPEFUL_MOODS:
        out = pa.build(quote="Know thyself.", mood=mood)
        hopecore = ("golden", "mist", "rain", "dawn", "soft",
                    "horizon", "rim light", "cliff")
        assert any(tok in out.lower() for tok in hopecore), \
            f"{mood} prompt missing hopecore keyword: {out}"


def test_explicit_photorealistic_skips_hopecore():
    pa = architect.PromptArchitect()
    out = pa.build(quote="Know thyself.", mood="cinematic_hopeful", style="photorealistic")
    assert "Phase One IQ4" in out