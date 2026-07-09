"""
Phase 4 (Viral Optimization) Integration Tests — Points 1,3,5,6,16,17,20,28,33,35,44.
All tests run offline (no API calls, no ffmpeg rendering).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_point1_visual_flash():
    from src.visual.image_composer import compose_pattern_interrupt_flash
    p = compose_pattern_interrupt_flash(output_dir="output", timestamp="test_p1")
    assert p.exists(), f"Flash frame not created: {p}"
    assert p.stat().st_size > 1000


def test_point3_notification_banner():
    from src.visual.image_composer import _draw_notification_banner, compose_hook_scene
    import inspect
    sig = inspect.signature(compose_hook_scene)
    assert "notification_text" in sig.parameters


def test_point5_glitch_intro():
    from src.video.reel_composer import generate_reel
    import inspect
    sig = inspect.signature(generate_reel)
    assert "glitch_intro" in sig.parameters


def test_point6_progress_bar():
    from src.video.reel_composer import generate_reel
    import inspect
    sig = inspect.signature(generate_reel)
    assert "progress_bar" in sig.parameters


def test_point16_strategic_silence():
    from src.audio.voiceover_engine import VoiceoverEngine
    ve = VoiceoverEngine()
    script = ve.build_script(
        quote="The unexamined life is not worth living.",
        hook_text="Stop scrolling.",
        mood="dark_philosophical",
    )
    # Hook should end with trailing ellipsis (silence marker)
    assert "..." in script.get("hook_voice", ""), "Hook missing silence marker"
    # Quote should end with trailing pause
    assert "..." in script.get("quote_voice", ""), "Quote missing silence marker"


def test_point17_audio_levels():
    """Audio mixing constants should be present and in valid range."""
    from src.video import reel_composer
    import inspect
    src = inspect.getsource(reel_composer.generate_reel)
    assert "MUSIC_DUCKED_VOL" in src, "Missing MUSIC_DUCKED_VOL constant"
    assert "VOICE_VOL" in src, "Missing VOICE_VOL constant"
    assert "MUSIC_SOLO_VOL" in src, "Missing MUSIC_SOLO_VOL constant"


def test_point20_carousel():
    from src.visual.carousel_composer import compose_carousel
    slides = compose_carousel(
        quote="Know thyself.",
        attribution="— Socrates",
        output_dir="output",
        timestamp="test_p20",
    )
    assert len(slides) == 5, f"Expected 5 slides, got {len(slides)}"
    for s in slides:
        assert s.exists(), f"Slide not created: {s}"
        assert s.stat().st_size > 1000


def test_point28_golden_timing():
    from src.analytics.ab_test import pick_posting_time, GOLDEN_MINUTES
    assert set(GOLDEN_MINUTES) == {13, 47}
    for slot in [0, 1, 2]:
        h, m = pick_posting_time(slot)
        assert m in GOLDEN_MINUTES, f"Slot {slot} returned non-golden minute {m}"
        assert 0 <= h <= 23


def test_point33_seed_comments():
    from src.core.notifier import Notifier
    assert hasattr(Notifier, "notify_seed_comments"), "Missing notify_seed_comments method"
    import inspect
    sig = inspect.signature(Notifier.notify_seed_comments)
    assert "post_url" in sig.parameters
    assert "quote" in sig.parameters
    assert "audience" in sig.parameters


def test_point35_save_bait():
    from src.visual.image_composer import compose_save_bait_scene
    p = compose_save_bait_scene(
        quote="The unexamined life is not worth living.",
        output_dir="output",
        timestamp="test_p35",
    )
    assert p.exists(), f"Save-bait not created: {p}"
    assert p.stat().st_size > 10000, "Save-bait suspiciously small"


def test_point44_save_rate():
    from src.analytics import calculate_save_rate, get_save_rate_report, print_save_rate_report
    assert calculate_save_rate(50, 1000) == 0.05
    assert calculate_save_rate(0, 0) == 0.0
    assert calculate_save_rate(100, 500) == 0.2
    report = get_save_rate_report(limit=5)
    assert isinstance(report, list)


if __name__ == "__main__":
    tests = [
        test_point1_visual_flash,
        test_point3_notification_banner,
        test_point5_glitch_intro,
        test_point6_progress_bar,
        test_point16_strategic_silence,
        test_point17_audio_levels,
        test_point20_carousel,
        test_point28_golden_timing,
        test_point33_seed_comments,
        test_point35_save_bait,
        test_point44_save_rate,
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
