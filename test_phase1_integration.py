"""
Phase 1 Integration Test — verifies all new viral modules load and function.

Run: python test_phase1_integration.py
"""

import sys
from pathlib import Path

def test_imports():
    """Verify all new modules import without error."""
    print("[TEST] Checking module imports...")
    try:
        from hooks.pattern_interrupt import PatternInterrupter
        from brand_design import BrandDesign, get_design
        from engagement.comment_bait import CommentBait
        from prompts.architect import PromptArchitect
        from wallpapers.composer import WallpaperComposer
        print("  All Phase 1 modules imported successfully")
        return True
    except Exception as e:
        print(f"  Import failed: {e}")
        return False


def test_pattern_interrupt():
    """Test pattern interrupt applies without crashing."""
    print("[TEST] PatternInterrupter...")
    try:
        from hooks.pattern_interrupt import PatternInterrupter
        from PIL import Image

        # Create dummy image
        img = Image.new("RGB", (1080, 1920), (50, 40, 30))

        for mode in ["notification", "color_flash", "zoom_burst", "glitch", "mixed"]:
            pi = PatternInterrupter(mode=mode)
            result = pi.apply(img, text="Test hook text", seed=42)
            assert result.size == (1080, 1920), f"Size mismatch for {mode}"
            print(f"    {mode}: OK ({result.mode})")

        # Test random mode
        random_mode = PatternInterrupter.random_mode(seed=42)
        print(f"    random_mode returned: {random_mode}")
        return True
    except Exception as e:
        print(f"  PatternInterrupter failed: {e}")
        return False


def test_brand_design():
    """Test brand design system."""
    print("[TEST] BrandDesign...")
    try:
        from brand_design import get_design

        for mood in ["dark_philosophical", "cinematic_hopeful", "calm_stoic", "epic_warrior"]:
            design = get_design(mood)
            assert design.colors is not None
            assert design.primary is not None
            print(f"    {mood}: primary={design.primary}")

        return True
    except Exception as e:
        print(f"  BrandDesign failed: {e}")
        return False


def test_comment_bait():
    """Test engagement question generator."""
    print("[TEST] CommentBait...")
    try:
        from engagement.comment_bait import CommentBait

        bait = CommentBait(audience="procrastinator", mood="dark_philosophical")

        for style in ["direct", "reflective", "confrontational", "supportive"]:
            q = bait.generate_question(style=style, quote="The unexamined life is not worth living.")
            assert len(q) > 10
            print(f"    {style}: {q[:50]}...")

        cta = bait.generate_cta(style="save_bait")
        print(f"    CTA: {cta[:50]}...")

        block = bait.generate_full_engagement_block(
            quote="Test quote", include_question=True, include_cta=True
        )
        assert len(block) > 20
        print(f"    Full block: {len(block)} chars")
        return True
    except Exception as e:
        print(f"  CommentBait failed: {e}")
        return False


def test_prompt_architect():
    """Test FLUX prompt builder."""
    print("[TEST] PromptArchitect...")
    try:
        from prompts.architect import PromptArchitect

        architect = PromptArchitect()
        prompt = architect.build(
            quote="Know thyself.",
            mood="mystical_greek",
            seed=42,
        )
        assert len(prompt) > 100
        assert "8k" in prompt.lower() or "hyper-detailed" in prompt.lower()
        print(f"    Prompt ({len(prompt)} chars): {prompt[:80]}...")

        # Test with base prompt
        enhanced = architect.build(
            quote="Test",
            mood="dark_philosophical",
            base_prompt="Ancient Greek ruins at night",
            seed=42,
        )
        assert "Ancient Greek ruins" in enhanced
        print(f"    Enhanced prompt: {enhanced[:80]}...")
        return True
    except Exception as e:
        print(f"  PromptArchitect failed: {e}")
        return False


def test_wallpaper_composer():
    """Test wallpaper creation (no actual image gen, just layout)."""
    print("[TEST] WallpaperComposer...")
    try:
        from wallpapers.composer import WallpaperComposer
        from PIL import Image

        composer = WallpaperComposer(mood="calm_stoic")

        # Create dummy background
        bg = Image.new("RGB", (1080, 1920), (30, 40, 35))

        results = composer.create_wallpaper_set(
            quote="The only true wisdom is in knowing you know nothing.",
            author="Socrates",
            output_dir="output/test_wallpapers",
            background_image=bg,
            seed=42,
        )
        assert len(results) >= 2  # at least vertical + square
        for fmt, path in results.items():
            assert path.exists(), f"Missing {fmt} wallpaper"
            print(f"    {fmt}: {path}")

        return True
    except Exception as e:
        print(f"  WallpaperComposer failed: {e}")
        return False


def test_pipeline_integration():
    """Verify pipeline.py has the correct Phase 1 imports (check source, don't import)."""
    print("[TEST] Pipeline integration...")
    try:
        pipeline_src = Path("pipeline.py").read_text()
        required = [
            "PatternInterrupter",
            "get_design",
            "CommentBait",
            "PromptArchitect",
            "WallpaperComposer",
        ]
        for name in required:
            assert name in pipeline_src, f"{name} not found in pipeline.py"
            print(f"    ✅ {name} import present")

        # Check key integration points
        assert "interrupter.apply(" in pipeline_src, "Pattern interrupt apply not wired"
        print("    ✅ interrupter.apply() wired")
        assert "CommentBait(audience=" in pipeline_src, "CommentBait not instantiated"
        print("    ✅ CommentBait instantiated")
        assert "architect.build(" in pipeline_src, "PromptArchitect build not wired"
        print("    ✅ PromptArchitect build() wired")
        assert "WallpaperComposer(" in pipeline_src, "WallpaperComposer not instantiated"
        print("    ✅ WallpaperComposer instantiated")
        assert "notify_wallpapers_ready(" in pipeline_src, "notify_wallpapers_ready not wired"
        print("    ✅ notify_wallpapers_ready wired")

        print("  ✅ pipeline.py fully wired for Phase 1")
        return True
    except Exception as e:
        print(f"  ❌ Pipeline integration failed: {e}")
        return False


def main():
    print("=" * 60)
    print("PHASE 1 VIRAL UPGRADE — INTEGRATION TEST")
    print("=" * 60)
    print()

    tests = [
        test_imports,
        test_pattern_interrupt,
        test_brand_design,
        test_comment_bait,
        test_prompt_architect,
        test_wallpaper_composer,
        test_pipeline_integration,
    ]

    results = []
    for test in tests:
        results.append(test())
        print()

    passed = sum(results)
    total = len(results)

    print("=" * 60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
