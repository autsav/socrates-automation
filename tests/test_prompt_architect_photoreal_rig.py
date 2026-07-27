"""Tests for Photorealism Rig always-on suffix in PromptArchitect."""
from src.prompts import architect

PHOTOREAL_RIG_SUBSTR = "Phase One IQ4"


def test_photoreal_rig_always_present():
    pa = architect.PromptArchitect()
    for mood in ("dark_philosophical", "cinematic_hopeful", "calm_stoic",
                 "dramatic_ancient", "epic_warrior", "mystical_greek",
                 "stark_minimal"):
        for style in ("mixed", "photorealistic", "painterly", "digital_art", "cinematic"):
            out = pa.build(quote="Know thyself.", mood=mood, style=style)
            assert PHOTOREAL_RIG_SUBSTR in out, \
                f"rig missing for mood={mood} style={style}: {out}"


def test_photoreal_rig_constant_defined():
    assert hasattr(architect.PromptArchitect, "PHOTOREAL_RIG")
    assert "35mm film grain" in architect.PromptArchitect.PHOTOREAL_RIG
    assert "no obvious 3D render" in architect.PromptArchitect.PHOTOREAL_RIG