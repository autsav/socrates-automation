import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw
from src.visual import image_composer as ic


def test_bundled_playfair_files_present():
    assert ic.PLAYFAIR_UPRIGHT.exists(), "bundled upright Playfair missing"
    assert ic.PLAYFAIR_ITALIC.exists(), "bundled italic Playfair missing"
    assert (ic.BUNDLED_FONT_DIR / "OFL.txt").exists(), "OFL license missing"


def test_load_font_uses_bundled_playfair_first():
    f = ic._load_font(48, bold=True)
    assert "PlayfairDisplay" in str(getattr(f, "path", "")), "should load bundled Playfair, not a system font"


def test_bold_is_heavier_than_regular():
    # Setting the weight axis to 900 must produce visibly heavier (wider) glyphs
    # than 400 — this proves the variable-font weight axis is actually applied.
    img = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(img)
    reg = ic._load_font(80, bold=False)
    bold = ic._load_font(80, bold=True)
    assert d.textlength("Wisdom", font=bold) > d.textlength("Wisdom", font=reg)
