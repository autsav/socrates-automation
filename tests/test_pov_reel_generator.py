import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock

from PIL import Image

from src.video.pov_reel_generator import (
    generate_pov_reel,
    generate_pov_reels,
    render_text_overlay,
    _build_gradient_background,
    _clamp_durations,
    _wrap_text,
    ffmpeg_available,
    OUTPUT_SIZE,
)


def test_ffmpeg_available_is_bool():
    assert isinstance(ffmpeg_available(), bool)


def test_gradient_background_size_and_mode():
    bg = _build_gradient_background(mood="dark_philosophical")
    assert bg.size == OUTPUT_SIZE
    assert bg.mode == "RGB"


def test_render_text_overlay_is_transparent_rgba_with_visible_text():
    overlay = render_text_overlay("A short punchy hook.", mood="dark_philosophical")
    assert overlay.size == OUTPUT_SIZE
    assert overlay.mode == "RGBA"
    # Some pixels must be non-transparent (the rendered text/shadow).
    alpha = overlay.split()[3]
    assert alpha.getextrema()[1] > 0


def test_render_text_overlay_wraps_long_quote_without_overflow():
    long_quote = "The unexamined life is not worth living, and yet most people never stop to examine anything at all, ever."
    overlay = render_text_overlay(long_quote, mood="calm_stoic")
    assert overlay.size == OUTPUT_SIZE
    alpha = overlay.split()[3]
    assert alpha.getextrema()[1] > 0


def test_wrap_text_splits_on_width():
    img = Image.new("RGB", (10, 10))
    from PIL import ImageDraw
    from src.visual.brand_design import BrandDesign
    draw = ImageDraw.Draw(img)
    font = BrandDesign().get_font(40, weight="bold")
    text = "one two three four five six seven eight"
    full_width = draw.textlength(text, font=font)
    max_width = full_width / 2  # force a wrap regardless of which font is resolved

    lines = _wrap_text(draw, text, font, max_width=max_width)
    assert len(lines) > 1
    assert all(draw.textlength(line, font=font) <= max_width + 1 for line in lines)


def test_clamp_durations_stays_within_bounds():
    hook, quote, cta = _clamp_durations(3.0, 2.0, 2.0)  # total 7.0 -> min bound
    assert hook + quote + cta >= 7.0

    hook, quote, cta = _clamp_durations(3.0, 20.0, 2.0)  # total 25 -> max bound
    assert hook + quote + cta <= 15.01


def test_generate_pov_reel_returns_none_without_ffmpeg(tmp_path):
    with patch("src.video.pov_reel_generator.ffmpeg_available", return_value=False):
        result = generate_pov_reel(
            quote="Know thyself.",
            hook="Read this.",
            cta="Save it.",
            output_path=tmp_path / "pov.mp4",
        )
    assert result is None


def test_generate_pov_reel_builds_expected_ffmpeg_command(tmp_path):
    """Mocked-ffmpeg unit test: verifies the command shape without actually encoding."""
    output_path = tmp_path / "pov.mp4"

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        output_path.write_bytes(b"fake-mp4-bytes")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    with patch("src.video.pov_reel_generator.ffmpeg_available", return_value=True), \
         patch("src.video.pov_reel_generator._resolve_audio", return_value=None), \
         patch("src.video.pov_reel_generator.subprocess.run", side_effect=fake_run):
        result = generate_pov_reel(
            quote="The unexamined life is not worth living.",
            hook="Socrates said something that will bother you all day.",
            cta="Save this before you forget it.",
            output_path=output_path,
        )

    assert result == output_path
    assert result.exists()
    cmd = captured["cmd"]
    assert "ffmpeg" in cmd
    assert "-filter_complex" in cmd
    assert "-an" in cmd  # no audio resolved -> silent output
    assert str(fps_flag_value(cmd)) == "30"


def fps_flag_value(cmd):
    idx = cmd.index("-r")
    return cmd[idx + 1]


def test_generate_pov_reel_real_ffmpeg_end_to_end(tmp_path):
    """Full integration: real ffmpeg run, no audio, small clip."""
    output_path = tmp_path / "pov_real.mp4"

    with patch("src.video.pov_reel_generator._resolve_audio", return_value=None):
        result = generate_pov_reel(
            quote="Know thyself.",
            hook="This is a test hook.",
            cta="Save this.",
            output_path=output_path,
            hook_duration=1.0,
            quote_duration=3.0,
            cta_duration=1.0,
            animate_background=False,
        )

    assert result is not None
    assert result.exists()
    assert result.suffix == ".mp4"
    assert result.stat().st_size > 1000


def test_generate_pov_reels_batch_mode(tmp_path):
    quotes = [
        {"quote": "Know thyself.", "audience": "stuck", "row_number": 1},
        {"quote": "", "audience": "lost", "row_number": 2},  # skipped: empty quote
        "Memento mori.",  # plain string form
    ]

    calls = []

    def fake_generate(quote, hook, cta, output_path, mood="dark_philosophical", **kwargs):
        calls.append((quote, hook, cta, mood))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"fake")
        return Path(output_path)

    with patch("src.video.pov_reel_generator.generate_pov_reel", side_effect=fake_generate):
        results = generate_pov_reels(quotes, output_dir=tmp_path)

    assert len(results) == 2  # empty-quote item skipped
    assert len(calls) == 2
    assert all(Path(p).exists() for p in results)


def test_generate_pov_reels_handles_generation_failure(tmp_path):
    def fake_generate(*args, **kwargs):
        raise RuntimeError("ffmpeg exploded")

    with patch("src.video.pov_reel_generator.generate_pov_reel", side_effect=fake_generate):
        results = generate_pov_reels(["Know thyself."], output_dir=tmp_path)

    assert results == []
