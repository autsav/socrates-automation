"""
Image Composer — overlays Socrates quote text on background image.
Uses Pillow with bundled system font fallbacks.
Output: 1080x1920 vertical JPEG ready for Instagram Reels.

Typography enhancements:
  - Gradient text (gold → white) for visual luxury
  - Text stroke/outline for readability on any background
  - Smart line spacing using actual font metrics
  - Multi-line hook with balanced word wrapping
  - Subtle panel drop shadow for depth
"""

import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

# ── Constants ─────────────────────────────────────────────────────────────────
OUTPUT_SIZE = (1080, 1920)   # 9:16 vertical for Instagram Reels
OVERLAY_OPACITY = 160        # 0-255: darkness of text overlay panel
GOLD_COLOR = (201, 169, 110) # #c9a96e
WHITE_COLOR = (245, 240, 232)
DARK_COLOR = (20, 18, 15)

# Instagram Reels safe zone: avoid top 15% and bottom 15% where UI overlays cover content
SAFE_TOP = int(OUTPUT_SIZE[1] * 0.15)
SAFE_BOTTOM = int(OUTPUT_SIZE[1] * 0.85)

BUNDLED_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
PLAYFAIR_UPRIGHT = BUNDLED_FONT_DIR / "PlayfairDisplay[wght].ttf"
PLAYFAIR_ITALIC = BUNDLED_FONT_DIR / "PlayfairDisplay-Italic[wght].ttf"


def _load_font(size: int, bold: bool = False, italic: bool = False):
    """Load system font or fallback to Pillow default.
    Supports bold and italic variants on Linux/Windows/macOS."""
    # Prefer the bundled Playfair Display variable font — consistent premium
    # typography everywhere, and never falls through to Pillow's bitmap default.
    bundled = PLAYFAIR_ITALIC if italic else PLAYFAIR_UPRIGHT
    if bundled.exists():
        try:
            f = ImageFont.truetype(str(bundled), size)
            try:
                f.set_variation_by_axes([900 if bold else 400])
            except Exception:
                pass  # non-variable build / axis unsupported — keep default instance
            return f
        except Exception:
            pass  # fall through to system fonts below

    # Build candidate lists based on requested style
    if bold:
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/Library/Fonts/Georgia Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
            "C:/Windows/Fonts/georgiab.ttf",
        ]
    elif italic:
        font_candidates = [
            "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
            "/Library/Fonts/Georgia Italic.ttf",
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


def _create_gradient_text(text: str, font: ImageFont.FreeTypeFont,
                          width: int, height: int,
                          start_color: tuple, end_color: tuple) -> Image.Image:
    """
    Render text with a vertical color gradient (e.g. gold → white).
    Returns an RGBA image with the gradient text.

    Uses font.getbbox() to compute the true glyph bounds (which can have
    negative x-offsets and non-zero y-offsets) and renders into a canvas
    large enough to avoid any clipping.
    """
    # Measure the true glyph bounds for this text + font
    bbox = font.getbbox(text)
    text_x0, text_y0, text_x1, text_y1 = bbox
    glyph_w = text_x1 - text_x0
    glyph_h = text_y1 - text_y0

    # Make the canvas large enough for the full glyph extents.
    # When text is drawn at (draw_x, draw_y), the actual pixel bounds are:
    #   x: draw_x + text_x0  to  draw_x + text_x1
    #   y: draw_y + text_y0  to  draw_y + text_y1
    # So the canvas must be at least (draw_x + text_x1, draw_y + text_y1).
    draw_x = 4  # small left padding
    draw_y = 4  # small top padding
    canvas_w = int(max(width, draw_x + text_x1 + 4))
    canvas_h = int(max(height, draw_y + text_y1 + 4))

    # Create a monochrome text mask
    mask = Image.new("L", (canvas_w, canvas_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((draw_x, draw_y), text, font=font, fill=255)

    # Build gradient image
    gradient = Image.new("RGB", (canvas_w, canvas_h))
    for y in range(canvas_h):
        ratio = y / max(canvas_h - 1, 1)
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        for x in range(canvas_w):
            gradient.putpixel((x, y), (r, g, b))

    # Composite gradient through text mask
    result = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    result.paste(gradient, (0, 0), mask)
    return result


def _draw_text_stroke(draw, text: str, font: ImageFont.FreeTypeFont,
                     x: int, y: int, fill: tuple, stroke_color: tuple = (0, 0, 0),
                     stroke_width: int = 2) -> None:
    """
    Draw text with an outline/stroke around every glyph.
    More reliable than glow for thin fonts and small sizes.
    """
    # Draw stroke by offsetting in 8 directions
    for dx, dy in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
        for w in range(1, stroke_width + 1):
            draw.text((x + dx * w, y + dy * w), text, font=font, fill=stroke_color)
    # Draw main text on top
    draw.text((x, y), text, font=font, fill=fill)


def _draw_text_centered(draw, text: str, font: ImageFont.FreeTypeFont,
                        y_center: int, width: int, color: tuple,
                        use_gradient: bool = False,
                        shadow: bool = True, stroke: bool = True) -> int:
    """
    Draw centered text with optional gradient, stroke, and shadow.
    Returns the Y coordinate of the bottom of the text block.
    """
    # Wrap text with word-aware balancing
    # Estimate chars per line based on font size
    char_width_px = font.size // 2 + 4
    max_chars = max(20, width // char_width_px)
    lines = _wrap_text_balanced(text, max_chars)

    # Use actual font metrics for accurate line height
    bbox = draw.textbbox((0, 0), "Mg", font=font)
    line_height = (bbox[3] - bbox[1]) + 12  # ascent+descent + padding

    total_height = len(lines) * line_height
    y = y_center - total_height // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2

        if use_gradient:
            # Render gradient text as an image and paste it
            text_h = bbox[3] - bbox[1]
            grad_img = _create_gradient_text(
                line, font, text_width, text_h,
                start_color=GOLD_COLOR,
                end_color=WHITE_COLOR,
            )
            # The gradient image has 4px padding on all sides, so the actual
            # glyph starts at (4, 4) inside the gradient image. We need to
            # paste at a position that aligns the glyph with where draw.text()
            # would have placed it at (x, y). Since draw.text() at (x, y) puts
            # the first glyph pixel at (x + bbox[0], y + bbox[1]), and the
            # gradient glyph is at (4, 4), we paste at:
            #   (x + bbox[0] - 4, y + bbox[1] - 4)
            paste_x = x + int(bbox[0]) - 4
            paste_y = y + int(bbox[1]) - 4
            if stroke:
                # Draw stroke underneath at the same position as the text
                _draw_text_stroke(draw, line, font, x, y, fill=(0, 0, 0, 0),
                                  stroke_color=(0, 0, 0), stroke_width=2)
            draw._image.paste(grad_img, (paste_x, paste_y), grad_img)
        elif stroke:
            _draw_text_stroke(draw, line, font, x, y, fill=color,
                              stroke_color=(0, 0, 0), stroke_width=2)
        elif shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 160))
            draw.text((x, y), line, font=font, fill=color)
        else:
            draw.text((x, y), line, font=font, fill=color)

        y += line_height

    return y


def _draw_panel_shadow(draw, left: int, top: int, right: int, bottom: int,
                       shadow_color: tuple = (0, 0, 0, 80), radius: int = 20) -> None:
    """Draw a blurred shadow behind a panel for depth."""
    # We need the parent image to paste onto
    img = draw._image
    shadow = Image.new("RGBA", (right - left + radius * 2, bottom - top + radius * 2), shadow_color)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=radius))
    img.paste(shadow, (left - radius, top - radius), shadow)


def generate_time_hook(hour: int | None = None) -> str:
    """
    Point 8: Personalised time hook.
    Generate a hook that references the current time for immediacy.
    """
    import datetime
    if hour is None:
        hour = datetime.datetime.now().hour
    minute = datetime.datetime.now().minute

    if 5 <= hour < 9:
        context = "You said you'd start early."
        return f"It's {hour}:{minute:02d} AM. {context}"
    elif 9 <= hour < 12:
        return f"It's {hour}:{minute:02d} AM. You said you'd start at 9:00."
    elif 12 <= hour < 14:
        return f"It's {hour}:{minute:02d}. You're scrolling instead of working."
    elif 14 <= hour < 18:
        return f"It's {hour}:{minute:02d}. There are still {18 - hour} hours left today."
    elif 18 <= hour < 22:
        return f"It's {hour}:{minute:02d} PM. What did you actually accomplish today?"
    else:
        return f"It's {hour}:{minute:02d}. You're awake. That's a choice."


def _draw_fomo_counter(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    y_pos: int = 200,
    count: int = 90,
) -> None:
    """
    Point 7: FOMO Counter overlay.
    "90% of people skip this" with a visual counter bar.
    """
    font_bold = _load_font(26, bold=True)
    font_small = _load_font(20)

    text_top = f"{count}% of people skip this."
    text_bot = "You didn't. That already says something."

    # Background pill
    pill_layer = Image.new("RGBA", (image_width, 200), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill_layer)
    pd.rounded_rectangle(
        [(60, y_pos), (image_width - 60, y_pos + 90)],
        radius=16,
        fill=(20, 20, 20, 210),
    )
    draw._image.paste(pill_layer, (0, 0), pill_layer)

    # Text
    bbox = draw.textbbox((0, 0), text_top, font=font_bold)
    tx = (image_width - (bbox[2] - bbox[0])) // 2
    draw.text((tx, y_pos + 14), text_top, font=font_bold, fill=(255, 200, 80))

    bbox2 = draw.textbbox((0, 0), text_bot, font=font_small)
    tx2 = (image_width - (bbox2[2] - bbox2[0])) // 2
    draw.text((tx2, y_pos + 52), text_bot, font=font_small, fill=(200, 200, 200))


def _draw_text_3d(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    fill: tuple,
    depth: int = 4,
    shadow_color: tuple = (0, 0, 0),
) -> None:
    """
    Point 10: 3D extruded text effect.
    Multiple offset shadow layers behind main text create depth/extrusion.
    """
    # Draw depth layers from back to front
    for d in range(depth, 0, -1):
        alpha = int(200 * (1 - d / depth))
        draw.text((x + d, y + d), text, font=font, fill=(*shadow_color, alpha))
    # Main text on top
    draw.text((x, y), text, font=font, fill=fill)


def compose_post(
    background_path: str | Path,
    quote: str,
    attribution: str = "— Socrates",
    output_dir: str = "output",
    timestamp: str = "post",
    quote_source: str = "socrates",  # "socrates" or "ai_generated"
    controversy_text: str = "",      # Optional: bold debate-starter bar at bottom
    pattern_interrupt_type: str = "", # Point 2: "inverted" | "light" | "" (default)
) -> Path:
    """
    Compose final Instagram post image.
    - Resize background to 1080x1920
    - Adaptive darkening overlay based on background brightness
    - Dynamic font sizing based on quote length
    - Gradient + stroke text for luxury readability
    - Decorative gold lines and Greek symbol
    - Smart attribution (Socrates vs AI-generated)
    - Optional controversy bar (red band + polarising question) for engagement
    - Point 2: pattern_interrupt_type="inverted" for colour-inverted variant
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

    # ── Quote text (with gradient + stroke) ───────────────────────────────────
    quote_font_size = _calculate_font_size(quote)
    quote_font = _load_font(quote_font_size, bold=True)
    quote_center_y = int(OUTPUT_SIZE[1] * 0.50)

    # Add opening quote mark
    _draw_text_stroke(draw, "“", _load_font(80), margin, line_y_top + 30,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

    _draw_text_centered(
        draw=draw,
        text=quote,
        font=quote_font,
        y_center=quote_center_y,
        width=OUTPUT_SIZE[0],
        color=WHITE_COLOR,
        use_gradient=True,
        stroke=True,
    )

    # ── Smart attribution ──────────────────────────────────────────────────────
    if quote_source == "ai_generated":
        attribution = "— Stoic Start"
    attr_font = _load_font(32, italic=True)
    attr_y = line_y_bottom - 52
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    attr_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_stroke(draw, attribution, attr_font, attr_x, attr_y,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

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

    # Point 2: Color Inversion Hook — inverted variant for A/B testing via Stories
    if pattern_interrupt_type == "inverted":
        from PIL import ImageOps
        final = ImageOps.invert(final)
    elif pattern_interrupt_type == "light":
        # Brighten significantly for light/washed variant
        final = ImageEnhance.Brightness(final).enhance(1.6)

    output_path = Path(output_dir) / f"post_{timestamp}.jpg"
    final.save(output_path, "JPEG", quality=95)

    # Auto-generate inverted variant for A/B testing if base variant
    if not pattern_interrupt_type:
        from PIL import ImageOps
        inv_path = Path(output_dir) / f"post_{timestamp}_inv.jpg"
        ImageOps.invert(final).save(inv_path, "JPEG", quality=95)

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
    for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1),(-2,0),(2,0),(0,-2),(0,2)]:
        draw.text((x+dx, y+dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))


# ── Scene composers for multi-scene Reels ────────────────────────────────────

# ── Phase 1 Viral Upgrades ────────────────────────────────────────────────────

def compose_pattern_interrupt_flash(
    output_dir: str = "output",
    timestamp: str = "flash",
    style: str = "red_shock",
) -> Path:
    """
    Point 1: Visual Hook Flash (0.4s pre-text).
    Jarring high-contrast frame inserted before Scene 1.
    Styles: red_shock | black_void | white_blast
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    if style == "red_shock":
        img.paste((180, 10, 10), [0, 0, OUTPUT_SIZE[0], OUTPUT_SIZE[1]])
        font = _load_font(120, bold=True)
        text = "!"
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
        y = (OUTPUT_SIZE[1] - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), text, font=font, fill=(255, 255, 255))
    elif style == "white_blast":
        img.paste((255, 255, 255), [0, 0, OUTPUT_SIZE[0], OUTPUT_SIZE[1]])
    # black_void: already black

    final = img.convert("RGB")
    out = out_dir / f"flash_{timestamp}.jpg"
    final.save(out, "JPEG", quality=95)
    return out


def _draw_notification_banner(
    draw: ImageDraw.ImageDraw,
    text: str,
    image_width: int,
    y_pos: int = 80,
) -> None:
    """
    Point 3: Fake iOS-style notification overlay.
    Pill-shaped banner with app icon area + message text.
    y_pos: top of the banner from image top.
    """
    banner_h = 88
    banner_w = image_width - 120
    banner_x = 60
    banner_y = y_pos
    radius = 22

    # Draw pill background (frosted dark)
    banner_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(banner_layer)
    b_draw.rounded_rectangle(
        [(banner_x, banner_y), (banner_x + banner_w, banner_y + banner_h)],
        radius=radius,
        fill=(30, 30, 30, 230),
    )
    draw._image.paste(banner_layer, (0, 0), banner_layer)

    # App icon dot
    icon_r = 18
    icon_cx = banner_x + 32
    icon_cy = banner_y + banner_h // 2
    icon_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    i_draw = ImageDraw.Draw(icon_layer)
    i_draw.ellipse(
        [(icon_cx - icon_r, icon_cy - icon_r), (icon_cx + icon_r, icon_cy + icon_r)],
        fill=(100, 180, 255, 255),
    )
    draw._image.paste(icon_layer, (0, 0), icon_layer)

    # Notification text (two lines: app name + message)
    app_font = _load_font(20, bold=True)
    msg_font = _load_font(24)
    text_x = banner_x + 62
    draw.text((text_x, banner_y + 14), "Instagram · now", font=app_font, fill=(160, 160, 160))
    draw.text((text_x, banner_y + 40), text, font=msg_font, fill=(245, 245, 245))


def compose_save_bait_scene(
    quote: str,
    attribution: str = "— Socrates",
    output_dir: str = "output",
    timestamp: str = "savebait",
    bg_color: tuple[int, int, int] = (15, 12, 8),
) -> Path:
    """
    Point 35: Save-bait frame — clean, screenshot-optimised.
    High contrast, no text cutoff, quote + attribution only.
    Designed so followers screenshot and save to camera roll.
    """
    img = Image.new("RGBA", OUTPUT_SIZE, (*bg_color, 255))
    draw = ImageDraw.Draw(img)

    # Subtle gold border
    margin = 60
    border_color = (*GOLD_COLOR, 180)
    border_layer = Image.new("RGBA", OUTPUT_SIZE, (0, 0, 0, 0))
    bd = ImageDraw.Draw(border_layer)
    bd.rectangle(
        [(margin, margin), (OUTPUT_SIZE[0] - margin, OUTPUT_SIZE[1] - margin)],
        outline=(*GOLD_COLOR, 140),
        width=3,
    )
    img.paste(border_layer, (0, 0), border_layer)

    # Large quote — fill 70% of frame vertically
    font_size = _calculate_font_size(quote) + 8  # slightly bigger for save-bait
    font = _load_font(font_size, bold=True)
    center_y = OUTPUT_SIZE[1] // 2 - 60

    _draw_text_centered(
        draw=draw,
        text=quote,
        font=font,
        y_center=center_y,
        width=OUTPUT_SIZE[0] - margin * 4,
        color=WHITE_COLOR,
        use_gradient=True,
        stroke=True,
    )

    # Attribution
    attr_font = _load_font(36, italic=True)
    attr_y = int(OUTPUT_SIZE[1] * 0.78)
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    attr_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_stroke(draw, attribution, attr_font, attr_x, attr_y,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

    # Save prompt
    prompt_font = _load_font(22)
    prompt = "Save this. You'll need it."
    bbox = draw.textbbox((0, 0), prompt, font=prompt_font)
    px = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((px, OUTPUT_SIZE[1] - 140), prompt, font=prompt_font,
              fill=(*GOLD_COLOR, 140))

    # Branding
    brand_font = _load_font(20)
    brand_text = "@stoic.start"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    bx = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((bx, OUTPUT_SIZE[1] - 80), brand_text, font=brand_font,
              fill=(*GOLD_COLOR, 120))

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = img.convert("RGB")
    out = out_dir / f"savebait_{timestamp}.jpg"
    final.save(out, "JPEG", quality=98)  # max quality for screenshotting
    return out


def compose_hook_scene(
    background_path: str | Path,
    hook_text: str,
    output_dir: str = "output",
    timestamp: str = "hook",
    controversy_text: str = "",   # Bold debate question at bottom
    notification_text: str = "",  # Point 3: fake iOS notification overlay
    fomo_counter: bool = False,   # Point 7: "90% of people skip this" overlay
    time_hook: bool = False,      # Point 8: current time injected into text
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
        use_gradient=True,
        stroke=True,
    )

    # Point 8: Time hook — inject current time into hook text
    if time_hook:
        time_text = generate_time_hook()
        t_font = _load_font(30, bold=True)
        bbox = draw.textbbox((0, 0), time_text, font=t_font)
        tx = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
        draw.text((tx, SAFE_TOP + 30), time_text, font=t_font, fill=(255, 220, 100))

    # Point 3: Fake notification overlay on hook scene
    if notification_text:
        _draw_notification_banner(draw, notification_text, OUTPUT_SIZE[0], y_pos=80)

    # Point 7: FOMO counter overlay
    if fomo_counter:
        _draw_fomo_counter(draw, OUTPUT_SIZE[0], y_pos=OUTPUT_SIZE[1] - 340)

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
    _draw_text_stroke(draw, "“", _load_font(80), margin, line_y_top + 30,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

    _draw_text_centered(
        draw=draw,
        text=quote,
        font=quote_font,
        y_center=quote_center_y,
        width=OUTPUT_SIZE[0],
        color=WHITE_COLOR,
        use_gradient=True,
        stroke=True,
    )

    # Attribution
    attr_font = _load_font(32, italic=True)
    attr_y = line_y_bottom - 52
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    attr_x = (OUTPUT_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_stroke(draw, attribution, attr_font, attr_x, attr_y,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

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
        use_gradient=True,
        stroke=True,
    )

    final = composite.convert("RGB")
    out = Path(output_dir) / f"scene_cta_{timestamp}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out, "JPEG", quality=95)
    return out


# ── Phase 3 Visual Upgrades ──────────────────────────────────────────────────

def add_letterbox_bars(
    image: Image.Image,
    ratio: float = 2.39,
) -> Image.Image:
    """
    Point 11: Cinematic 2.39:1 letterbox bars.
    Adds black bars top+bottom to simulate widescreen framing.
    ratio: aspect ratio of the "visible" window (2.39 = Scope).
    """
    w, h = image.size
    visible_h = int(w / ratio)
    bar_h = (h - visible_h) // 2
    if bar_h <= 0:
        return image
    result = image.copy()
    bar = Image.new("RGB", (w, bar_h), (0, 0, 0))
    result.paste(bar, (0, 0))
    result.paste(bar, (0, h - bar_h))
    return result


def generate_gradient_mesh_bg(
    mood: str = "dark_philosophical",
    size: tuple[int, int] = OUTPUT_SIZE,
    seed: int = 0,
) -> Image.Image:
    """
    Point 12: Procedural gradient mesh background.
    Free alternative to FLUX — uses multi-point colour interpolation.
    No API cost. Use when FLUX fails or for A/B testing.
    """
    import random as _random
    if seed:
        _random.seed(seed)

    from src.visual.brand_design import MOOD_PALETTES
    palette = MOOD_PALETTES.get(mood, MOOD_PALETTES["dark_philosophical"])
    c1 = palette["primary"]
    c2 = palette["secondary"]
    c3 = palette["accent"]
    accent = palette.get("accent_glow", c3)

    w, h = size
    img = Image.new("RGB", (w, h))
    pixels = img.load()

    # 4-corner gradient mesh
    corners = [
        _random.choice([c1, c2]),
        _random.choice([c2, c1]),
        _random.choice([c1, c3]),
        _random.choice([c3, accent]),
    ]

    for y in range(h):
        for x in range(w):
            fx, fy = x / w, y / h
            top = tuple(int(corners[0][i] * (1 - fx) + corners[1][i] * fx) for i in range(3))
            bot = tuple(int(corners[2][i] * (1 - fx) + corners[3][i] * fx) for i in range(3))
            px = tuple(int(top[i] * (1 - fy) + bot[i] * fy) for i in range(3))
            pixels[x, y] = px

    # Add fine noise for texture (pure Pillow — no numpy needed)
    try:
        import numpy as _np
        arr = _np.array(img, dtype=_np.int16)
        _rng = _np.random.default_rng(seed)
        noise = _rng.integers(-10, 11, arr.shape, dtype=_np.int16)
        arr = _np.clip(arr + noise, 0, 255).astype(_np.uint8)
        return Image.fromarray(arr)
    except ModuleNotFoundError:
        # numpy not available — return without noise
        return img


def _draw_qr_placeholder(
    draw: ImageDraw.ImageDraw,
    url: str,
    x: int,
    y: int,
    size: int = 120,
) -> None:
    """
    Point 13: QR code placeholder.
    Draws a compact URL text block at (x, y) styled as a QR badge.
    Full QR requires the 'qrcode' package; this is a dependency-free fallback.
    """
    # Border box
    draw.rectangle([(x, y), (x + size, y + size)], outline=GOLD_COLOR, width=2)
    draw.rectangle([(x + 4, y + 4), (x + size - 4, y + size - 4)], fill=(0, 0, 0, 200))

    # URL text
    font = _load_font(14)
    # Wrap URL to fit
    short_url = url.replace("https://", "").replace("http://", "")
    lines = [short_url[i:i+16] for i in range(0, min(len(short_url), 64), 16)]
    ty = y + 8
    for line in lines[:5]:
        bbox = draw.textbbox((0, 0), line, font=font)
        lx = x + (size - (bbox[2] - bbox[0])) // 2
        draw.text((lx, ty), line, font=font, fill=WHITE_COLOR)
        ty += 18

    # "QR" label
    lbl_font = _load_font(12, bold=True)
    draw.text((x + 4, y + size - 20), "scan", font=lbl_font, fill=(*GOLD_COLOR, 160))


def add_qr_to_image(
    image: Image.Image,
    url: str,
    position: str = "bottom_right",
    size: int = 120,
) -> Image.Image:
    """
    Point 13: Add QR code (or URL badge) to an image.
    position: "bottom_right" | "bottom_left" | "top_right"
    """
    result = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(result)
    w, h = result.size
    margin = 20

    if position == "bottom_right":
        x, y = w - size - margin, h - size - margin - 80
    elif position == "bottom_left":
        x, y = margin, h - size - margin - 80
    else:
        x, y = w - size - margin, margin + 80

    _draw_qr_placeholder(draw, url, x, y, size)
    return result.convert("RGB")


BORDER_STYLES = {
    "minimal": {
        "description": "Single thin gold line",
        "draw": lambda draw, w, h, m: draw.rectangle([(m, m), (w-m, h-m)], outline=GOLD_COLOR, width=2),
    },
    "double_line": {
        "description": "Two parallel gold lines",
        "draw": lambda draw, w, h, m: (
            draw.rectangle([(m, m), (w-m, h-m)], outline=GOLD_COLOR, width=2),
            draw.rectangle([(m+8, m+8), (w-m-8, h-m-8)], outline=(*GOLD_COLOR, 120), width=1),
        ),
    },
    "ornate": {
        "description": "Corner flourishes",
        "draw": "_ornate_border",
    },
    "gradient": {
        "description": "Gold to transparent gradient border",
        "draw": "_gradient_border",
    },
    "glow": {
        "description": "Soft glow border",
        "draw": "_glow_border",
    },
}


def _draw_border_ornate(draw: ImageDraw.ImageDraw, w: int, h: int, m: int) -> None:
    """Ornate border: thin frame + corner L-brackets."""
    draw.rectangle([(m, m), (w-m, h-m)], outline=(*GOLD_COLOR, 80), width=1)
    cs = 40  # corner size
    for cx, cy in [(m, m), (w-m, m), (m, h-m), (w-m, h-m)]:
        dx = 1 if cx == m else -1
        dy = 1 if cy == m else -1
        draw.line([(cx, cy), (cx + dx*cs, cy)], fill=GOLD_COLOR, width=3)
        draw.line([(cx, cy), (cx, cy + dy*cs)], fill=GOLD_COLOR, width=3)


def add_border(
    image: Image.Image,
    style: str = "minimal",
    margin: int = 40,
) -> Image.Image:
    """
    Point 15: Apply a border style to an image.
    style: minimal | double_line | ornate | gradient | glow
    """
    result = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(result)
    w, h = result.size

    if style == "minimal":
        draw.rectangle([(margin, margin), (w-margin, h-margin)], outline=(*GOLD_COLOR, 200), width=2)
    elif style == "double_line":
        draw.rectangle([(margin, margin), (w-margin, h-margin)], outline=(*GOLD_COLOR, 200), width=2)
        draw.rectangle([(margin+8, margin+8), (w-margin-8, h-margin-8)], outline=(*GOLD_COLOR, 100), width=1)
    elif style == "ornate":
        _draw_border_ornate(draw, w, h, margin)
    elif style == "glow":
        # Glow via blurred border layer
        glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.rectangle([(margin, margin), (w-margin, h-margin)], outline=(*GOLD_COLOR, 180), width=6)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))
        result = Image.alpha_composite(result, glow_layer)
    elif style == "gradient":
        # Fade gold border top→bottom
        for i, y_val in enumerate(range(margin, margin+4)):
            alpha = int(200 * (1 - i/4))
            draw.line([(margin, y_val), (w-margin, y_val)], fill=(*GOLD_COLOR, alpha))
        draw.rectangle([(margin, margin), (w-margin, h-margin)], outline=(*GOLD_COLOR, 100), width=1)

    return result.convert("RGB")


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
