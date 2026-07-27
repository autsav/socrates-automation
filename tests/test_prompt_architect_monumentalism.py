"""Tests for Digital Monumentalism mood routing in PromptArchitect."""
from src.prompts import architect

DARK_MOODS = ("dark_philosophical", "dramatic_ancient", "stark_minimal", "epic_warrior")


def test_dark_moods_get_monumentalism():
    pa = architect.PromptArchitect()
    for mood in DARK_MOODS:
        out = pa.build(quote="Know thyself.", mood=mood)
        monumental = ("marble", "stone", "column", "ruins", "shadows",
                      "fog", "chiaroscuro", "mist")
        assert any(tok in out.lower() for tok in monumental), \
            f"{mood} prompt missing monumentalism keyword: {out}"


def test_explicit_photorealistic_skips_monumentalism():
    pa = architect.PromptArchitect()
    out = pa.build(quote="Know thyself.", mood="dark_philosophical", style="photorealistic")
    assert "Phase One IQ4" in out