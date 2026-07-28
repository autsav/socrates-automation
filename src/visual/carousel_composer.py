"""
Carousel Composer — Point 20: 5-slide carousel optimisation.

Slide structure (psychology-driven for saves + reach):
  1. Hook question  — curiosity gap, forces swipe
  2. Quote full     — the wisdom, clean + beautiful
  3. Context        — why this quote matters today
  4. Breakdown      — actionable takeaway / key insight
  5. CTA + attr     — save / share / follow prompt

Output: 5 × 1080x1080 JPEGs (square for carousel feed post).
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.visual.image_composer import (
    _load_font, _draw_text_centered, _draw_text_stroke,
    _wrap_text_balanced, GOLD_COLOR, WHITE_COLOR, DARK_COLOR,
    OUTPUT_SIZE,
)

# Carousel uses 1:1 square format
CAROUSEL_SIZE = (1080, 1080)

# Branding
BRAND = "@stoic.start"


def _bg_for_carousel(
    bg_path: str | Path | None,
    color: tuple[int, int, int] = (15, 12, 8),
) -> Image.Image:
    """Return a 1080×1080 background: resize from path or solid colour."""
    if bg_path and Path(bg_path).exists():
        img = Image.open(bg_path).convert("RGBA")
        # Crop center square
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize(CAROUSEL_SIZE, Image.LANCZOS)
        # Darken
        overlay = Image.new("RGBA", CAROUSEL_SIZE, (0, 0, 0, 140))
        img = Image.alpha_composite(img, overlay)
    else:
        img = Image.new("RGBA", CAROUSEL_SIZE, (*color, 255))
    return img


def _add_branding(draw: ImageDraw.ImageDraw, slide_num: int, total: int) -> None:
    """Bottom bar: brand handle + slide indicator dots."""
    font = _load_font(20)
    bbox = draw.textbbox((0, 0), BRAND, font=font)
    bx = (CAROUSEL_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((bx, CAROUSEL_SIZE[1] - 48), BRAND, font=font, fill=(*GOLD_COLOR, 140))

    # Dot indicators
    dot_r = 5
    total_dot_w = total * (dot_r * 2 + 6) - 6
    dot_start_x = (CAROUSEL_SIZE[0] - total_dot_w) // 2
    dot_y = CAROUSEL_SIZE[1] - 22
    for i in range(total):
        cx = dot_start_x + i * (dot_r * 2 + 6) + dot_r
        fill = GOLD_COLOR if i == slide_num - 1 else (80, 70, 55)
        draw.ellipse([(cx - dot_r, dot_y - dot_r), (cx + dot_r, dot_y + dot_r)], fill=fill)


def compose_slide_hook(
    question: str,
    bg_path: str | Path | None = None,
    output_dir: str = "output",
    timestamp: str = "carousel",
) -> Path:
    """Slide 1: Hook question — large, centred, forces swipe."""
    img = _bg_for_carousel(bg_path, color=(12, 8, 4))
    draw = ImageDraw.Draw(img)

    # Gold decorative top bar
    draw.line([(60, 80), (CAROUSEL_SIZE[0] - 60, 80)], fill=GOLD_COLOR, width=2)

    # "SWIPE →" label at top right
    lbl_font = _load_font(22, bold=True)
    lbl = "SWIPE →"
    bbox = draw.textbbox((0, 0), lbl, font=lbl_font)
    draw.text((CAROUSEL_SIZE[0] - bbox[2] - bbox[0] - 40, 50), lbl,
              font=lbl_font, fill=(*GOLD_COLOR, 180))

    # Hook question — big and confrontational
    font = _load_font(58, bold=True)
    _draw_text_centered(
        draw=draw,
        text=question,
        font=font,
        y_center=CAROUSEL_SIZE[1] // 2 - 30,
        width=CAROUSEL_SIZE[0] - 100,
        color=WHITE_COLOR,
        use_gradient=True,
        stroke=True,
    )

    draw.line([(60, CAROUSEL_SIZE[1] - 70), (CAROUSEL_SIZE[0] - 60, CAROUSEL_SIZE[1] - 70)],
              fill=GOLD_COLOR, width=1)
    _add_branding(draw, 1, 5)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"carousel_1_hook_{timestamp}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=95)
    return out


def compose_slide_quote(
    quote: str,
    attribution: str = "— Socrates",
    bg_path: str | Path | None = None,
    output_dir: str = "output",
    timestamp: str = "carousel",
) -> Path:
    """Slide 2: Full quote — the centrepiece."""
    img = _bg_for_carousel(bg_path, color=(16, 12, 8))
    draw = ImageDraw.Draw(img)

    # Gold lines
    draw.line([(80, 120), (CAROUSEL_SIZE[0] - 80, 120)], fill=GOLD_COLOR, width=2)
    draw.line([(80, CAROUSEL_SIZE[1] - 120), (CAROUSEL_SIZE[0] - 80, CAROUSEL_SIZE[1] - 120)],
              fill=GOLD_COLOR, width=2)

    # Opening quote mark
    qm_font = _load_font(72)
    draw.text((80, 90), "“", font=qm_font, fill=(*GOLD_COLOR, 180))

    # Σ symbol
    sym_font = _load_font(24)
    draw.text((CAROUSEL_SIZE[0] // 2 - 10, 88), "Σ", font=sym_font, fill=GOLD_COLOR)

    # Quote text
    font_size = max(36, min(52, 2600 // max(len(quote), 1)))
    font = _load_font(font_size, bold=True)
    _draw_text_centered(
        draw=draw, text=quote, font=font,
        y_center=CAROUSEL_SIZE[1] // 2 - 20,
        width=CAROUSEL_SIZE[0] - 120,
        color=WHITE_COLOR, use_gradient=True, stroke=True,
    )

    # Attribution
    attr_font = _load_font(28, italic=True)
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    ax = (CAROUSEL_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_stroke(draw, attribution, attr_font, ax, CAROUSEL_SIZE[1] - 140,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

    _add_branding(draw, 2, 5)

    out = Path(output_dir) / f"carousel_2_quote_{timestamp}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=95)
    return out


def compose_slide_context(
    context_text: str,
    bg_path: str | Path | None = None,
    output_dir: str = "output",
    timestamp: str = "carousel",
) -> Path:
    """Slide 3: Context — why this matters today."""
    img = _bg_for_carousel(bg_path, color=(10, 8, 14))
    draw = ImageDraw.Draw(img)

    # Header label
    lbl_font = _load_font(24, bold=True)
    lbl = "WHY IT MATTERS"
    bbox = draw.textbbox((0, 0), lbl, font=lbl_font)
    lx = (CAROUSEL_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((lx, 90), lbl, font=lbl_font, fill=(*GOLD_COLOR, 200))
    draw.line([(lx, 122), (lx + bbox[2] - bbox[0], 122)], fill=GOLD_COLOR, width=1)

    font = _load_font(40)
    _draw_text_centered(
        draw=draw, text=context_text, font=font,
        y_center=CAROUSEL_SIZE[1] // 2,
        width=CAROUSEL_SIZE[0] - 120,
        color=WHITE_COLOR, use_gradient=False, stroke=True,
    )

    _add_branding(draw, 3, 5)

    out = Path(output_dir) / f"carousel_3_context_{timestamp}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=95)
    return out


def compose_slide_breakdown(
    takeaway: str,
    bg_path: str | Path | None = None,
    output_dir: str = "output",
    timestamp: str = "carousel",
) -> Path:
    """Slide 4: Actionable takeaway / key insight."""
    img = _bg_for_carousel(bg_path, color=(8, 12, 10))
    draw = ImageDraw.Draw(img)

    lbl_font = _load_font(24, bold=True)
    lbl = "THE TAKEAWAY"
    bbox = draw.textbbox((0, 0), lbl, font=lbl_font)
    lx = (CAROUSEL_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((lx, 90), lbl, font=lbl_font, fill=(*GOLD_COLOR, 200))
    draw.line([(lx, 122), (lx + bbox[2] - bbox[0], 122)], fill=GOLD_COLOR, width=1)

    font = _load_font(44, bold=True)
    _draw_text_centered(
        draw=draw, text=takeaway, font=font,
        y_center=CAROUSEL_SIZE[1] // 2,
        width=CAROUSEL_SIZE[0] - 120,
        color=WHITE_COLOR, use_gradient=True, stroke=True,
    )

    _add_branding(draw, 4, 5)

    out = Path(output_dir) / f"carousel_4_breakdown_{timestamp}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=95)
    return out


def compose_slide_cta(
    cta_text: str = "Save this. Someone you know needs it.",
    attribution: str = "— Socrates",
    bg_path: str | Path | None = None,
    output_dir: str = "output",
    timestamp: str = "carousel",
) -> Path:
    """Slide 5: CTA + attribution — save/share trigger."""
    img = _bg_for_carousel(bg_path, color=(18, 10, 6))
    draw = ImageDraw.Draw(img)

    # Bold CTA centred
    font = _load_font(52, bold=True)
    _draw_text_centered(
        draw=draw, text=cta_text, font=font,
        y_center=CAROUSEL_SIZE[1] // 2 - 40,
        width=CAROUSEL_SIZE[0] - 120,
        color=GOLD_COLOR, use_gradient=False, stroke=True,
    )

    # Save icon hint (text)
    save_font = _load_font(28)
    save_lbl = "♡  Save  ·  Share  ·  Follow"
    bbox = draw.textbbox((0, 0), save_lbl, font=save_font)
    sx = (CAROUSEL_SIZE[0] - (bbox[2] - bbox[0])) // 2
    draw.text((sx, CAROUSEL_SIZE[1] // 2 + 120), save_lbl, font=save_font,
              fill=(*GOLD_COLOR, 160))

    # Attribution
    attr_font = _load_font(26, italic=True)
    bbox = draw.textbbox((0, 0), attribution, font=attr_font)
    ax = (CAROUSEL_SIZE[0] - (bbox[2] - bbox[0])) // 2
    _draw_text_stroke(draw, attribution, attr_font, ax, CAROUSEL_SIZE[1] - 130,
                      fill=GOLD_COLOR, stroke_color=(0, 0, 0), stroke_width=2)

    _add_branding(draw, 5, 5)

    out = Path(output_dir) / f"carousel_5_cta_{timestamp}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=95)
    return out


def compose_carousel(
    quote: str,
    attribution: str = "— Socrates",
    hook_question: str = "",
    context_text: str = "",
    takeaway: str = "",
    cta_text: str = "Save this. Someone you know needs it.",
    bg_path: str | Path | None = None,
    output_dir: str = "output",
    timestamp: str = "carousel",
) -> list[Path]:
    """
    Point 20: Compose a full 5-slide carousel.
    Auto-generates hook/context/takeaway from quote if not provided.
    Returns list of 5 image paths in slide order.
    """
    if not hook_question:
        hook_question = _auto_hook(quote)
    if not context_text:
        context_text = _auto_context(quote)
    if not takeaway:
        takeaway = _auto_takeaway(quote)

    slides = [
        compose_slide_hook(hook_question, bg_path, output_dir, timestamp),
        compose_slide_quote(quote, attribution, bg_path, output_dir, timestamp),
        compose_slide_context(context_text, bg_path, output_dir, timestamp),
        compose_slide_breakdown(takeaway, bg_path, output_dir, timestamp),
        compose_slide_cta(cta_text, attribution, bg_path, output_dir, timestamp),
    ]
    logger.info(f"  [carousel] 5 slides → {output_dir}/carousel_*_{timestamp}.jpg")
    return slides


def _auto_hook(quote: str) -> str:
    """Generate a hook question from the quote."""
    hooks = [
        "What if everything you believe about productivity is wrong?",
        "Are you living — or just existing?",
        "What would you start today if failure wasn't an option?",
        "When did you stop asking yourself the hard questions?",
        "The thing holding you back isn't what you think it is.",
    ]
    # Pick deterministically based on quote hash
    return hooks[hash(quote) % len(hooks)]


def _auto_context(quote: str) -> str:
    """Generate a why-it-matters blurb."""
    contexts = [
        "Written over 2,400 years ago. Still hitting harder than anything posted today.",
        "Ancient wisdom for the most distracted generation in history.",
        "Socrates was killed for asking this question. Are you brave enough to answer it?",
        "This isn't philosophy. This is a mirror.",
        "They didn't have phones. They had time. And they still chose discomfort.",
    ]
    return contexts[hash(quote) % len(contexts)]


def _auto_takeaway(quote: str) -> str:
    """Generate an actionable takeaway."""
    takeaways = [
        "Stop reading. Start doing one thing.",
        "Name the one thing you've been avoiding. Then do it.",
        "Discomfort is the price of growth. Pay it.",
        "The examined life starts with one honest question.",
        "You already know what to do. The question is: will you?",
    ]
    return takeaways[hash(quote) % len(takeaways)]


if __name__ == "__main__":
    # Quick smoke test
    slides = compose_carousel(
        quote="The unexamined life is not worth living.",
        attribution="— Socrates",
        output_dir="output",
        timestamp="test",
    )
    for s in slides:
        logger.info(f"  Slide: {s}")
