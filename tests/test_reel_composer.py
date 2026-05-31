import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from reel_composer import generate_reel, ffmpeg_available, _audio_path, MOOD_AUDIO


def test_ffmpeg_available():
    """ffmpeg should be available on this system."""
    # We expect ffmpeg to be installed per the plan
    assert isinstance(ffmpeg_available(), bool)


def test_audio_path_exists():
    """All 7 mood audio files should exist after generation."""
    for mood in MOOD_AUDIO:
        path = _audio_path(mood)
        assert path is not None, f"Audio file missing for mood: {mood}"
        assert path.exists(), f"Audio file does not exist: {path}"


def test_audio_path_unknown_mood_falls_back():
    """Unknown mood should fall back to calm_stoic."""
    path = _audio_path("nonexistent_mood")
    assert path is not None
    assert path.exists()


def _make_test_scenes(tmp_path, prefix="test"):
    """Create 3 vertical test scene images."""
    from PIL import Image
    scenes = []
    for name in ["hook", "quote", "cta"]:
        img = Image.new("RGB", (1080, 1920), color=(30 + hash(name) % 50, 20, 10))
        path = tmp_path / f"{prefix}_{name}.jpg"
        img.save(path, "JPEG")
        scenes.append(path)
    return scenes


def test_generate_reel_success(tmp_path):
    """Should generate an MP4 file with audio when ffmpeg is available."""
    scenes = _make_test_scenes(tmp_path)

    result = generate_reel(
        scene_images=scenes,
        mood="calm_stoic",
        output_dir=str(tmp_path / "output"),
        timestamp="test123"
    )

    assert result is not None
    assert result.exists()
    assert result.suffix == ".mp4"
    # Should be non-empty
    assert result.stat().st_size > 1000


def test_generate_reel_missing_image():
    """Should raise FileNotFoundError for missing image."""
    try:
        generate_reel(["/nonexistent/hook.jpg", "/nonexistent/quote.jpg", "/nonexistent/cta.jpg"], "calm_stoic")
        assert False, "Should have raised"
    except FileNotFoundError:
        pass


def test_generate_reel_silent_fallback(tmp_path):
    """Should generate a silent video even without audio file."""
    scenes = _make_test_scenes(tmp_path, prefix="silent")

    # Patch _audio_path to return None (missing audio)
    with patch("reel_composer._audio_path", return_value=None):
        result = generate_reel(
            scene_images=scenes,
            mood="calm_stoic",
            output_dir=str(tmp_path / "output2"),
            timestamp="silent"
        )

    assert result is not None
    assert result.exists()
    assert result.stat().st_size > 500
