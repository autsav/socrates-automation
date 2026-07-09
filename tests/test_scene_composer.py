import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image
from src.visual.image_composer import (
    compose_hook_scene,
    compose_quote_scene,
    compose_cta_scene,
    OUTPUT_SIZE,
)


def _make_bg(tmp_path, size=OUTPUT_SIZE):
    """Create a test background image."""
    bg = tmp_path / "bg.jpg"
    Image.new("RGB", size, color=(30, 20, 10)).save(bg, "JPEG")
    return bg


def test_compose_hook_scene_creates_vertical_image(tmp_path):
    """Hook scene should be 1080x1920 vertical."""
    bg = _make_bg(tmp_path)
    result = compose_hook_scene(
        background_path=bg,
        hook_text="Stop scrolling. Start living.",
        output_dir=str(tmp_path),
        timestamp="test",
    )
    assert result.exists()
    img = Image.open(result)
    assert img.size == (1080, 1920)


def test_compose_quote_scene_creates_vertical_image(tmp_path):
    """Quote scene should be 1080x1920 vertical with quote text."""
    bg = _make_bg(tmp_path)
    result = compose_quote_scene(
        background_path=bg,
        quote="The unexamined life is not worth living.",
        attribution="— Socrates",
        output_dir=str(tmp_path),
        timestamp="test",
    )
    assert result.exists()
    img = Image.open(result)
    assert img.size == (1080, 1920)


def test_compose_cta_scene_creates_vertical_image(tmp_path):
    """CTA scene should be 1080x1920 vertical."""
    bg = _make_bg(tmp_path)
    result = compose_cta_scene(
        background_path=bg,
        cta_text="Save this. Read it again tonight.",
        output_dir=str(tmp_path),
        timestamp="test",
    )
    assert result.exists()
    img = Image.open(result)
    assert img.size == (1080, 1920)


def test_compose_hook_scene_custom_text(tmp_path):
    """Hook scene should accept custom hook text."""
    bg = _make_bg(tmp_path)
    result = compose_hook_scene(
        background_path=bg,
        hook_text="Custom hook text here",
        output_dir=str(tmp_path),
        timestamp="custom",
    )
    assert "scene_hook_custom.jpg" in str(result)


def test_extract_hook_first_sentence():
    """Should extract first sentence from caption."""
    from pipeline import _extract_hook
    caption = "Still scrolling? Here's what Socrates would say. Stop wasting your life."
    hook = _extract_hook(caption)
    assert hook == "Still scrolling? Here's what Socrates would say"


def test_extract_hook_truncation():
    """Should truncate long first sentence with ellipsis."""
    from pipeline import _extract_hook
    long_caption = "This is an extremely long first sentence that goes on and on and on forever without any period in sight"
    hook = _extract_hook(long_caption, max_chars=30)
    assert len(hook) <= 33  # 30 + "..."
    assert hook.endswith("...")
