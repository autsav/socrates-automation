"""
Phase 1 Integration Test — verifies all new viral modules load and function.

Real pytest tests: assertions propagate (a failure FAILS the test). Previously
each body was wrapped in try/except → return True/False, which swallowed
AssertionError and made every test pass unconditionally. `main()` is kept as a
manual smoke runner (`python -m tests.test_phase1_integration`).
"""

import sys
from pathlib import Path


def test_imports():
    """Verify all new modules import without error."""
    from src.hooks.pattern_interrupt import PatternInterrupter
    from src.visual.brand_design import BrandDesign, get_design
    from src.engagement.comment_bait import CommentBait
    from src.prompts.architect import PromptArchitect
    from src.wallpapers.composer import WallpaperComposer


def test_pattern_interrupt():
    """Test pattern interrupt applies without crashing."""
    from src.hooks.pattern_interrupt import PatternInterrupter
    from PIL import Image

    img = Image.new("RGB", (1080, 1920), (50, 40, 30))
    for mode in ["notification", "color_flash", "zoom_burst", "glitch", "mixed"]:
        pi = PatternInterrupter(mode=mode)
        result = pi.apply(img, text="Test hook text", seed=42)
        assert result.size == (1080, 1920), f"Size mismatch for {mode}"

    PatternInterrupter.random_mode(seed=42)


def test_brand_design():
    """Test brand design system."""
    from src.visual.brand_design import get_design

    for mood in ["dark_philosophical", "cinematic_hopeful", "calm_stoic", "epic_warrior"]:
        design = get_design(mood)
        assert design.colors is not None
        assert design.primary is not None


def test_comment_bait():
    """Test engagement question generator."""
    from src.engagement.comment_bait import CommentBait

    bait = CommentBait(audience="procrastinator", mood="dark_philosophical")
    for style in ["direct", "reflective", "confrontational", "supportive"]:
        q = bait.generate_question(style=style, quote="The unexamined life is not worth living.")
        assert len(q) > 10

    bait.generate_cta(style="save_bait")
    block = bait.generate_full_engagement_block(
        quote="Test quote", include_question=True, include_cta=True
    )
    assert len(block) > 20


def test_prompt_architect():
    """Test FLUX prompt builder."""
    from src.prompts.architect import PromptArchitect

    architect = PromptArchitect()
    prompt = architect.build(quote="Know thyself.", mood="mystical_greek", seed=42)
    assert len(prompt) > 100
    # Photorealism Rig (always-on suffix, task 15) replaces the old "8k/hyper-detailed" tail
    assert "phase one iq4" in prompt.lower() or "photorealistic" in prompt.lower()

    enhanced = architect.build(
        quote="Test", mood="dark_philosophical",
        base_prompt="Ancient Greek ruins at night", seed=42,
    )
    assert "Ancient Greek ruins" in enhanced


def test_wallpaper_composer(tmp_path):
    """Test wallpaper creation (real layout composition)."""
    from src.wallpapers.composer import WallpaperComposer
    from PIL import Image

    composer = WallpaperComposer(mood="calm_stoic")
    bg = Image.new("RGB", (1080, 1920), (30, 40, 35))
    results = composer.create_wallpaper_set(
        quote="The only true wisdom is in knowing you know nothing.",
        author="Socrates",
        output_dir=str(tmp_path / "wallpapers"),
        background_image=bg,
        seed=42,
    )
    assert len(results) >= 2  # at least vertical + square
    for fmt, path in results.items():
        assert Path(path).exists(), f"Missing {fmt} wallpaper"


def test_pipeline_integration():
    """Verify pipeline.py has the correct Phase 1 imports (check source, don't import)."""
    pipeline_src = (Path(__file__).parent.parent / "pipeline.py").read_text()
    for name in ["PatternInterrupter", "get_design", "CommentBait", "PromptArchitect", "WallpaperComposer"]:
        assert name in pipeline_src, f"{name} not found in pipeline.py"

    assert "interrupter.apply(" in pipeline_src, "Pattern interrupt apply not wired"
    assert "CommentBait(audience=" in pipeline_src, "CommentBait not instantiated"
    assert "architect.build(" in pipeline_src, "PromptArchitect build not wired"
    assert "WallpaperComposer(" in pipeline_src, "WallpaperComposer not instantiated"
    assert "notify_wallpapers_ready(" in pipeline_src, "notify_wallpapers_ready not wired"


def main():
    """Manual smoke runner — raises (non-zero exit) on the first failing test."""
    import tempfile
    tests = [
        test_imports, test_pattern_interrupt, test_brand_design, test_comment_bait,
        test_prompt_architect, test_pipeline_integration,
    ]
    for t in tests:
        t()
    with tempfile.TemporaryDirectory() as d:
        test_wallpaper_composer(Path(d))
    print("All Phase 1 integration tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
