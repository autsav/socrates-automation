"""
Phase 3 Integration Test — verifies trending audio and voiceover engines.
"""

import sys
from pathlib import Path

def test_trending_audio_engine():
    """Test TrendingAudioEngine loads and has fallback tracks."""
    print("[TEST] TrendingAudioEngine...")
    try:
        from trending_audio import TrendingAudioEngine, FALLBACK_TRACKS

        engine = TrendingAudioEngine(cache_dir="output/test_audio_cache")
        assert len(FALLBACK_TRACKS) >= 7  # one per mood
        print(f"    Fallback tracks: {len(FALLBACK_TRACKS)} moods")

        # Test metadata persistence
        tracks = engine.list_cached_tracks()
        print(f"    Cached tracks: {len(tracks)}")

        # Test suggestion
        suggestion = engine.suggest_trending_sound("dark_philosophical")
        print(f"    Suggestion: {suggestion[:50]}...")

        return True
    except Exception as e:
        print(f"  TrendingAudioEngine failed: {e}")
        return False


def test_voiceover_engine():
    """Test VoiceoverEngine script building (no API calls)."""
    print("[TEST] VoiceoverEngine...")
    try:
        from voiceover_engine import VoiceoverEngine, ProsodyConfig

        engine = VoiceoverEngine(api_key="test")

        # Test script generation
        scripts = engine.build_script(
            quote="The unexamined life is not worth living.",
            hook_text="Stop scrolling.",
            cta_text="Save this.",
            mood="dark_philosophical",
            style="intense",
        )
        assert "quote_voice" in scripts
        assert "hook_voice" in scripts
        assert "cta_voice" in scripts
        print(f"    Hook: {scripts['hook_voice'][:50]}...")
        print(f"    Quote: {scripts['quote_voice'][:50]}...")
        print(f"    CTA: {scripts['cta_voice'][:50]}...")

        # Test voice selection
        voice = engine.pick_voice("epic_warrior")
        assert voice == "onyx"
        print(f"    Voice for epic_warrior: {voice}")

        voice = engine.pick_voice("mystical_greek")
        assert voice == "shimmer"
        print(f"    Voice for mystical_greek: {voice}")

        # Test configs
        configs = engine._scene_configs("calm_stoic", "calm")
        assert configs["quote"].emotion == "reflective"
        assert configs["quote"].speed == "slow"
        print(f"    Calm quote config: {configs['quote'].emotion}, {configs['quote'].speed}")

        # Test demo voices
        voices = VoiceoverEngine.demo_voices()
        assert len(voices) == 6
        print(f"    Available voices: {len(voices)}")

        return True
    except Exception as e:
        print(f"  VoiceoverEngine failed: {e}")
        return False


def test_pipeline_integration():
    """Verify pipeline.py has Phase 3 imports."""
    print("[TEST] Pipeline integration...")
    try:
        pipeline_src = Path("pipeline.py").read_text()
        assert "TrendingAudioEngine" in pipeline_src
        assert "VoiceoverEngine" in pipeline_src
        assert "generate_enhanced_voiceover" in pipeline_src
        assert "download_music_for_mood" in pipeline_src
        print("    All Phase 3 imports present in pipeline.py")

        # Check reel_composer too
        reel_src = Path("reel_composer.py").read_text()
        assert "trending_audio" in reel_src
        print("    reel_composer.py wired for trending audio")

        return True
    except Exception as e:
        print(f"  Pipeline integration failed: {e}")
        return False


def main():
    print("=" * 60)
    print("PHASE 3 INTEGRATION TEST")
    print("=" * 60)
    print()

    tests = [
        test_trending_audio_engine,
        test_voiceover_engine,
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
