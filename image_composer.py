"""
Image Composer — overlays Socrates quote text on background image.
Uses Pillow with bundled system font fallbacks.
Output: 1080x1920 vertical JPEG ready for Instagram Reels.
"""

import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Constants ─────────────────────────────────────────────────────────────────
OUTPUT_SIZE = (1080, 1920)   # 9:16 vertical for Instagram Reels
OVERLAY_OPACITY = 160        # 0-255: darkness of text overlay panel
GOLD_COLOR = (201, 169, 110) # #c9a96e
WHITE_COLOR = (245, 240, 232)
DARK_COLOR = (20, 18, 15)

# Instagram Reels safe zone: avoid top 15% and bottom 15% where UI overlays cover content
SAFE_TOP = int(OUTPUT_SIZE[1] * 0.15)
SAFE_BOTTOM = int(OUTPUT_SIZE[1] * 0.85)


def _load_font(size: int, bold: bool = False, italic: bool = False):
    """Load system font or fallback to Pillow default.
    Supports bold and italic variants on Linux/Windows."""
    # Build candidate lists based on requested style
    if bold:
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
            "C:/Windows/Fonts/georgiab.ttf",
        ]
    elif italic:
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
            "C:/Windows/Fonts/georgiai.ttf",
        ]
    else:
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/Library/Fonts/Georgia.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
            "C:/Windows/Fonts/georgia.ttf",
        ]

    for path in font_candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Final fallback — Pillow built-in
    return ImageFont.load_default()


def _calculate_font_size(quote: str) -> int:
    """Return optimal quote font size based on character count."""
    length = len(quote)
    if length <= 80:
        return 64
    elif length <= 150:
        return 52
    elif length <= 220:
        return 42
    else:
        return 36


def _analyze_brightness(bg: Image.Image, region: tuple) -> float:
    """Analyze average brightness of a background region (0=dark, 255=bright).
    region = (left, top, right, bottom)."""
    cropped = bg.crop(region).convert("L")
    # Resize to 1x1 to get average quickly
    small = cropped.resize((1, 1), Image.LANCZOS)
    return small.getpixel((0, 0))


def _draw_text_glow(draw, text, font, x, y, color, glow_color=(0, 0, 0), radius=8):
    """Draw text with a soft outer glow for readability on busy backgrounds."""
    # Create a temporary image for the glow mask
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if w <= 0 or h <= 0:
        return

    # Create mask of just the text
    mask = Image.new("L", (w + radius * 2, h + radius * 2), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((radius, radius), text, font=font, fill=255)
    # Blur the mask to create glow
    glow = mask.filter(ImageFilter.GaussianBlur(radius=radius))
    # Paste glow onto the main image
    draw._image.paste(glow_color, (x - radius, y - radius), glow)
    # Draw the actual text on top
    draw.text((x, y), text, font=font, fill=color)


def _wrap_text_balanced(text: str, max_chars: int) -> list[str]:
    """Wrap text into lines, preferring word boundaries and minimizing raggedness."""
    if len(text) <= max_chars:
        return [text]

    words = text.split()
    lines = []
    current = []
    current_len = 0

    for word in words:
        word_len = len(word)
        if current_len + word_len + len(current) > max_chars and current:
            lines.append(" ".join(current))
            current = [word]
            current_len = word_len
        else:
            current.append(word)
            current_len += word_len

    if current:
        lines.append(" ".join(current))

    return lines


def _draw_text_centered(draw, text, font, y_center, width, color, shadow=True, glow=True):
    """Draw centered text with optional outer glow for readability."""
    # Wrap text with word-aware balancing
    char_width = width // (font.size // 2 + 4)
    lines = _wrap_text_balanced(text, char_width)

    line_height = font.size + 8
    total_height = len(lines) * line_height
    y = y_center - total_height // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2

        if glow:
            _draw_text_glow(draw, line, font, x, y, color, glow_color=(0, 0, 0), radius=10)
        elif shadow:
            # Simple drop shadow fallback
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font, fill=color)
        else:
            draw.text((x, y), line, font=font, fill=color)

        y += line_height

    return y  # Return bottom y position


def compose_post(
    background_path: str | Path,
    quote: str,
    attribution: str = "— Socrates",
    output_dir: str = "output",
    timestamp: str = "post",
    quote_source: str = "socrates",  # "socrates" or "ai_generated"
    controversy_text: str = "",      # Optional: bold debate-starter bar at bottom
) -> Path:
    """
    Compose final Instagram post image.
    - Resize background to 1080x1920
    - Adaptive darkening overlay based on background brightness
    - Dynamic font sizing based on quote length
    - Text glow for readability on busy backgrounds
    - Decorative gold lines and Greek symbol
    - Smart attribution (Socrates vs AI-generated)
    - Optional controversy bar (red band + polarising question) for engagement
    Returns path to final JPEG.
    """
    bg_path = Path(background_path)
    if not bg_path.exists():
        raise FileNotFoundError(f"Background image not found: {bg_path}")

    # ── Load + resize background ──────────────────────────────────────────────
    bg = Image.open(bg_path).convert("RGBA")
    bg = bg.resize(OUTPUT_SIZE, Image.LANCZOS)

    # ── Analyze background brightness for adaptive overlay ──────────────────
    panel_top    = int(OUTPUT_SIZE[1] * 0.25)
    panel_bottom = int(OUTPUT_SIZE[1] * 0.75)
    brightness = _analyze_brightness(bg, (80, panel_top, OUTPUT_SIZE[0] - 80, panel_bottom))
    # If background is already dark (brightness < 80), reduce overlay opacity
    adaptive_opacity = max(120, min(OVERLAY_OPACITY, int(OVERLAY_OPACITY * (brightness / 128))))

    # ── Darkening overlay ───────────────────────────────────────────────────
    overlay = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rectangle(
        [(80, panel_top), (OUTPUT_SIZE[0] - 80, panel_bottom)],
        fill=(10, 8, 6, adaptive_opacity)
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=12))
    composite = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(composite)

    # ── Gold decorative lines ─────────────────────────────────────────────────
    line_y_top    = int(OUTPUT_SIZE[1] * 0.28)
    line_y_bottom = int(OUTPUT_SIZE[1] * 0.72)
    margin = 120

    for y in [line_y_top, line_y_bottom]:
        draw.line([(margin, y), (OUTPUT_SIZE[0] - margin, y)], fill=GOLD_COLOR, width=2)

    # ── Small Greek symbol (decorative) ───────────────────────────────────────
    symbol_font = _load_font(28)
    draw.text(
        (OUTPUT_SIZE[0] // 2 - 10, line_y_top - 42),
        "Σ",
        font=symbol_font,
        fill=GOLD_COLOR,
        anchor=None
    )

    # ── Quote text ────────────────────────────────────────────────────────────
    quote_font_size = _calculate_font_size(quote)
    quote_font = _load_font(quote_font_size, bold=True)
    quote_center_y = int(OUTPUT_SIZE[1] * 0.50)

    # Add opening quote mark
    draw.text((margin, line_y_top + 30), "“", font=_load_font(80), fill=GOLD_COLOR)

    _draw_text_centered(
        draw=draw,
        text=quote,
        font=quote_font,
        y_center=quote_center_y,
        width=OUTPUT_SIZE[0],
        color=WHITE_COLOR,
        glow=True,
    )

    # ── Smart attribution ──────────────────────────────────────────────────────
    if quote_source == "ai_generated":
        attribution = "— Stoic Start"
    attr_font = _load_font(32, italic=True)
    attr_y = line_y_bottom - 52
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    attr_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_glow(draw, attribution, attr_font, attr_x, attr_y, GOLD_COLOR, glow_color=(0, 0, 0), radius=6)

    # ── Branding (bottom) ─────────────────────────────────────────────────────
    brand_font = _load_font(22)
    brand_text = "@stoic.start"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    brand_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((brand_x, OUTPUT_SIZE[1] - 80), brand_text, font=brand_font, fill=(*GOLD_COLOR, 160))

    # ── Controversy overlay (optional) ───────────────────────────────────────
    if controversy_text:
        _draw_controversy_overlay(draw, controversy_text, OUTPUT_SIZE[0], OUTPUT_SIZE[1], _load_font)

    # ── Save final image ──────────────────────────────────────────────────────
    final = composite.convert("RGB")  # Instagram requires JPEG (no alpha)
    output_path = Path(output_dir) / f"post_{timestamp}.jpg"
    final.save(output_path, "JPEG", quality=95)

    return output_path


def _draw_controversy_overlay(draw, text: str, image_width: int, image_height: int, font_loader):
    """
    Draw a high-contrast controversy bar at the bottom of the image.
    Psychology: polarising statements + binary questions force comments.
    Style: bold white text on semi-transparent dark red/charcoal band.
    """
    bar_height = 90
    bar_top = image_height - 200
    bar_bottom = bar_top + bar_height

    # Draw semi-transparent dark band
    from PIL import Image as PILImage
    bar_overlay = PILImage.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
    bar_draw = ImageDraw.Draw(bar_overlay)
    bar_draw.rectangle(
        [(0, bar_top), (image_width, bar_bottom)],
        fill=(140, 20, 20, 210)  # Deep red, high visibility
    )
    draw._image.paste(
        PILImage.new("RGBA", (image_width, bar_height), (140, 20, 20, 210)),
        (0, bar_top),
        PILImage.new("RGBA", (image_width, bar_height), (140, 20, 20, 210)),
    )

    # Draw controversy text centered in the bar
    font = font_loader(28, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (image_width - text_w) // 2
    y = bar_top + (bar_height - text_h) // 2

    # White text with black outline for max contrast
    for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
        draw.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))


# ── Scene composers for multi-scene Reels ────────────────────────────────────

def compose_hook_scene(
    background_path: str | Path,
    hook_text: str,
    output_dir: str = "output",
    timestamp: str = "hook",
    controversy_text: str = "",   # Bold debate question at bottom
) -> Path:
    """
    Compose a scroll-stopping hook frame (Scene 1).
    Large bold text + optional controversy bar — pure attention grabber.
    """
    bg = Image.open(background_path).convert("RGBA")
    bg = bg.resize(OUTPUT_SIZE, Image.LANCZOS)

    overlay = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    draw_o = ImageDraw.Draw(overlay)

    # Slightly darker overlay for text readability
    panel_top = SAFE_TOP
    panel_bottom = SAFE_BOTTOM
    draw_o.rectangle(
        [(40, panel_top), (OUTPUT_SIZE[0] - 40, panel_bottom)],
        fill=(10, 8, 6, 140)
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=8))
    composite = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(composite)

    # Large bold hook text centered in safe zone
    hook_font = _load_font(72, bold=True)
    hook_center_y = OUTPUT_SIZE[1] // 2
    _draw_text_centered(
        draw=draw,
        text=hook_text,
        font=hook_font,
        y_center=hook_center_y,
        width=OUTPUT_SIZE[0],
        color=WHITE_COLOR,
        glow=True,
    )

    # Controversy bar on hook scene — drives comments from first frame
    if controversy_text:
        _draw_controversy_overlay(draw, controversy_text, OUTPUT_SIZE[0], OUTPUT_SIZE[1], _load_font)

    final = composite.convert("RGB")
    out = Path(output_dir) / f"scene_hook_{timestamp}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out, "JPEG", quality=95)
    return out


def compose_quote_scene(
    background_path: str | Path,
    quote: str,
    attribution: str = "— Socrates",
    output_dir: str = "output",
    timestamp: str = "quote",
) -> Path:
    """
    Compose a quote frame for Reel Scene 2.
    Similar to compose_post but as a standalone scene image.
    """
    bg = Image.open(background_path).convert("RGBA")
    bg = bg.resize(OUTPUT_SIZE, Image.LANCZOS)

    overlay = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    draw_o = ImageDraw.Draw(overlay)

    panel_top = int(OUTPUT_SIZE[1] * 0.25)
    panel_bottom = int(OUTPUT_SIZE[1] * 0.75)
    draw_o.rectangle(
        [(80, panel_top), (OUTPUT_SIZE[0] - 80, panel_bottom)],
        fill=(10, 8, 6, OVERLAY_OPACITY)
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=12))
    composite = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(composite)

    # Decorative lines
    line_y_top = int(OUTPUT_SIZE[1] * 0.28)
    line_y_bottom = int(OUTPUT_SIZE[1] * 0.72)
    margin = 120
    for y in [line_y_top, line_y_bottom]:
        draw.line([(margin, y), (OUTPUT_SIZE[0] - margin, y)], fill=GOLD_COLOR, width=2)

    # Greek symbol
    symbol_font = _load_font(28)
    draw.text(
        (OUTPUT_SIZE[0] // 2 - 10, line_y_top - 42),
        "Σ",
        font=symbol_font,
        fill=GOLD_COLOR,
    )

    # Quote
    quote_font_size = _calculate_font_size(quote)
    quote_font = _load_font(quote_font_size, bold=True)
    quote_center_y = int(OUTPUT_SIZE[1] * 0.50)
    draw.text((margin, line_y_top + 30), "“", font=_load_font(80), fill=GOLD_COLOR)

    _draw_text_centered(
        draw=draw,
        text=quote,
        font=quote_font,
        y_center=quote_center_y,
        width=OUTPUT_SIZE[0],
        color=WHITE_COLOR,
        glow=True,
    )

    # Attribution
    attr_font = _load_font(32, italic=True)
    attr_y = line_y_bottom - 52
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    attr_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_glow(draw, attribution, attr_font, attr_x, attr_y, GOLD_COLOR, glow_color=(0, 0, 0), radius=6)

    # Branding
    brand_font = _load_font(22)
    brand_text = "@stoic.start"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    brand_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((brand_x, OUTPUT_SIZE[1] - 80), brand_text, font=brand_font, fill=(*GOLD_COLOR, 160))

    final = composite.convert("RGB")
    out = Path(output_dir) / f"scene_quote_{timestamp}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out, "JPEG", quality=95)
    return out


def compose_cta_scene(
    background_path: str | Path,
    cta_text: str = "Save this. Read it again tonight.",
    output_dir: str = "output",
    timestamp: str = "cta",
) -> Path:
    """
    Compose a call-to-action frame (Scene 3).
    Dark overlay with centered CTA text.
    """
    bg = Image.open(background_path).convert("RGBA")
    bg = bg.resize(OUTPUT_SIZE, Image.LANCZOS)

    # Darker overlay than other scenes
    overlay = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 180))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=6))
    composite = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(composite)

    # CTA text centered
    cta_font = _load_font(48)
    cta_center_y = OUTPUT_SIZE[1] // 2
    _draw_text_centered(
        draw=draw,
        text=cta_text,
        font=cta_font,
        y_center=cta_center_y,
        width=OUTPUT_SIZE[0],
        color=GOLD_COLOR,
        shadow=True,
    )

    final = composite.convert("RGB")
    out = Path(output_dir) / f"scene_cta_{timestamp}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out, "JPEG", quality=95)
    return out


if __name__ == "__main__":
    # Test with a solid color background
    _project_root = Path(__file__).parent.resolve()
    test_bg = _project_root / "output" / "test_bg.jpg"
    test_bg.parent.mkdir(parents=True, exist_ok=True)

    # Create test gradient background
    test_img = Image.new("RGB", (1024, 1820), color=(30, 20, 10))
    test_img.save(test_bg)

    result = compose_post(
        background_path=test_bg,
        quote="The unexamined life is not worth living. Stop scrolling and start becoming.",
        attribution="— Socrates",
        timestamp="test"
    )
    print(f"Composed: {result}")
