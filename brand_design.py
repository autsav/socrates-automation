"""
Brand Design System — centralized visual identity for Socrates content.

Provides:
  - Color palettes per mood (psychology-informed)
  - Font registry with fallbacks
  - Texture overlay paths
  - Layout presets (hook, quote, CTA scene compositions)
  - Dynamic typography sizing

Usage:
    from brand_design import BrandDesign, MOOD_PALETTES
    design = BrandDesign(mood="dark_philosophical")
    colors = design.colors
    font = design.get_font(size=64, weight="bold")
"""

import random
from pathlib import Path
from PIL import Image, ImageFont, ImageDraw, ImageFilter

# ── Color Palettes (psychology-informed) ─────────────────────────────────────
# Each mood has a primary, secondary, accent, and text color.
# Primary: dominant background tone
# Secondary: supporting element tone
# Accent: call-to-action / highlight
# Text: guaranteed readable against primary background

MOOD_PALETTES = {
    "dark_philosophical": {
        "primary": (15, 12, 10),         # Deep obsidian
        "secondary": (40, 35, 30),      # Warm dark brown
        "accent": (201, 169, 110),        # Classic gold (#c9a96e)
        "accent_glow": (255, 215, 140),   # Light gold for glow
        "text": (245, 240, 232),          # Warm white
        "text_secondary": (180, 170, 155),# Muted warm gray
        "overlay_alpha": 180,             # Dark panel opacity
        "gradient_start": (201, 169, 110),# Gold
        "gradient_end": (245, 240, 232),  # White
    },
    "dramatic_ancient": {
        "primary": (25, 15, 10),          # Ancient terracotta dark
        "secondary": (60, 35, 20),       # Burnt sienna
        "accent": (220, 95, 50),          # Terracotta (#dc5f32)
        "accent_glow": (255, 140, 90),    # Bright terracotta
        "text": (255, 248, 235),          # Parchment white
        "text_secondary": (200, 185, 160),
        "overlay_alpha": 175,
        "gradient_start": (220, 95, 50),
        "gradient_end": (255, 248, 235),
    },
    "cinematic_hopeful": {
        "primary": (10, 20, 35),          # Deep twilight blue
        "secondary": (25, 45, 70),       # Steel blue
        "accent": (100, 180, 255),        # Sky blue (#64b4ff)
        "accent_glow": (150, 210, 255),   # Light sky
        "text": (255, 255, 255),          # Pure white
        "text_secondary": (180, 200, 220),
        "overlay_alpha": 160,
        "gradient_start": (100, 180, 255),
        "gradient_end": (255, 255, 255),
    },
    "stark_minimal": {
        "primary": (240, 240, 240),       # Clean white-gray
        "secondary": (200, 200, 200),     # Light gray
        "accent": (30, 30, 30),           # Charcoal
        "accent_glow": (60, 60, 60),      # Dark gray
        "text": (20, 20, 20),             # Near black
        "text_secondary": (100, 100, 100),
        "overlay_alpha": 140,
        "gradient_start": (30, 30, 30),
        "gradient_end": (80, 80, 80),
    },
    "epic_warrior": {
        "primary": (20, 10, 10),          # Blood-red dark
        "secondary": (50, 20, 15),        # Deep crimson
        "accent": (220, 60, 40),          # Warrior red (#dc3c28)
        "accent_glow": (255, 100, 70),    # Bright red
        "text": (255, 245, 235),          # Warm white
        "text_secondary": (200, 180, 165),
        "overlay_alpha": 170,
        "gradient_start": (220, 60, 40),
        "gradient_end": (255, 245, 235),
    },
    "mystical_greek": {
        "primary": (15, 10, 30),          # Deep violet
        "secondary": (40, 25, 60),        # Dark purple
        "accent": (180, 120, 255),        # Mystic violet (#b478ff)
        "accent_glow": (210, 170, 255),   # Soft violet
        "text": (245, 240, 255),          # Lavender white
        "text_secondary": (180, 165, 200),
        "overlay_alpha": 170,
        "gradient_start": (180, 120, 255),
        "gradient_end": (245, 240, 255),
    },
    "calm_stoic": {
        "primary": (18, 25, 22),          # Deep olive
        "secondary": (35, 50, 40),        # Forest green
        "accent": (140, 190, 140),        # Sage green (#8cbe8c)
        "accent_glow": (180, 220, 180),   # Light sage
        "text": (250, 250, 245),          # Off white
        "text_secondary": (190, 195, 180),
        "overlay_alpha": 165,
        "gradient_start": (140, 190, 140),
        "gradient_end": (250, 250, 245),
    },
}

# Default palette if mood not found
DEFAULT_PALETTE = MOOD_PALETTES["dark_philosophical"]


# ── Font Registry ────────────────────────────────────────────────────────────
# Searches for high-quality fonts in priority order.

_FONT_CANDIDATES = {
    "regular": [
        ("PlayfairDisplay-Regular.ttf", "/usr/share/fonts/truetype/playfair/"),
        ("Merriweather-Regular.ttf", "/usr/share/fonts/truetype/merriweather/"),
        ("Cinzel-Regular.ttf", "/usr/share/fonts/truetype/cinzel/"),
        ("Georgia.ttf", "/usr/share/fonts/truetype/dejavu/"),
        ("DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/"),
        ("LiberationSerif-Regular.ttf", "/usr/share/fonts/truetype/liberation/"),
        ("FreeSerif.ttf", "/usr/share/fonts/truetype/freefont/"),
    ],
    "bold": [
        ("PlayfairDisplay-Bold.ttf", "/usr/share/fonts/truetype/playfair/"),
        ("Merriweather-Bold.ttf", "/usr/share/fonts/truetype/merriweather/"),
        ("Cinzel-Bold.ttf", "/usr/share/fonts/truetype/cinzel/"),
        ("DejaVuSerif-Bold.ttf", "/usr/share/fonts/truetype/dejavu/"),
        ("LiberationSerif-Bold.ttf", "/usr/share/fonts/truetype/liberation/"),
        ("FreeSerifBold.ttf", "/usr/share/fonts/truetype/freefont/"),
    ],
    "italic": [
        ("PlayfairDisplay-Italic.ttf", "/usr/share/fonts/truetype/playfair/"),
        ("Merriweather-Italic.ttf", "/usr/share/fonts/truetype/merriweather/"),
        ("DejaVuSerif-Italic.ttf", "/usr/share/fonts/truetype/dejavu/"),
        ("LiberationSerif-Italic.ttf", "/usr/share/fonts/truetype/liberation/"),
        ("FreeSerifItalic.ttf", "/usr/share/fonts/truetype/freefont/"),
    ],
}

# Also check a local fonts/ directory
_LOCAL_FONT_DIR = Path(__file__).parent / "fonts"


def _find_font(weight: str = "regular", size: int = 64) -> ImageFont.FreeTypeFont:
    """Find and load the best available font for the given weight."""
    candidates = _FONT_CANDIDATES.get(weight, _FONT_CANDIDATES["regular"])

    for filename, sys_dir in candidates:
        # Check local fonts dir first
        local_path = _LOCAL_FONT_DIR / filename
        if local_path.exists():
            try:
                return ImageFont.truetype(str(local_path), size)
            except Exception:
                continue
        # Check system dir
        sys_path = Path(sys_dir) / filename
        if sys_path.exists():
            try:
                return ImageFont.truetype(str(sys_path), size)
            except Exception:
                continue

    # Final fallback
    return ImageFont.load_default()


# ── Texture Overlays ─────────────────────────────────────────────────────────
# Paths to subtle noise/grain textures that add depth

_TEXTURE_DIR = Path(__file__).parent / "textures"


def _get_texture(name: str) -> Image.Image | None:
    """Load a texture overlay if available."""
    path = _TEXTURE_DIR / f"{name}.png"
    if path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    return None


# ── Dynamic Typography Sizing ──────────────────────────────────────────────

def calculate_font_size(text: str, base_size: int = 64, min_size: int = 32) -> int:
    """
    Calculate optimal font size based on text length.
    Longer text = smaller font to fit screen.
    """
    length = len(text)
    if length <= 60:
        return base_size
    elif length <= 120:
        return int(base_size * 0.85)
    elif length <= 180:
        return int(base_size * 0.72)
    elif length <= 250:
        return int(base_size * 0.62)
    else:
        return max(min_size, int(base_size * 0.55))


def calculate_line_count(text: str, max_chars_per_line: int = 28) -> int:
    """Estimate how many lines the text will need."""
    words = text.split()
    lines = 0
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > max_chars_per_line and current_len > 0:
            lines += 1
            current_len = len(word)
        else:
            current_len += len(word) + 1
    if current_len > 0:
        lines += 1
    return lines


# ── Main Brand Design Class ──────────────────────────────────────────────────

class BrandDesign:
    """
    Centralized design system for a given mood.
    Handles colors, fonts, textures, and layout decisions.
    """

    OUTPUT_SIZE = (1080, 1920)
    SAFE_TOP = int(OUTPUT_SIZE[1] * 0.15)
    SAFE_BOTTOM = int(OUTPUT_SIZE[1] * 0.85)

    def __init__(self, mood: str = "dark_philosophical"):
        self.mood = mood
        self.colors = MOOD_PALETTES.get(mood, DEFAULT_PALETTE)
        self.palette = self.colors  # alias

    # ── Font Loading ──────────────────────────────────────────────────────────

    def get_font(self, size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
        """Load a font at the given size and weight."""
        return _find_font(weight=weight, size=size)

    def get_quote_font_size(self, quote: str) -> int:
        """Determine optimal quote font size based on length and line count."""
        length = len(quote)
        lines = calculate_line_count(quote)

        # If lots of lines, reduce size further
        if lines <= 3:
            return calculate_font_size(quote, base_size=72)
        elif lines <= 5:
            return calculate_font_size(quote, base_size=64)
        elif lines <= 7:
            return calculate_font_size(quote, base_size=56)
        else:
            return calculate_font_size(quote, base_size=48)

    # ── Color Access ──────────────────────────────────────────────────────────

    @property
    def primary(self) -> tuple:
        return self.colors["primary"]

    @property
    def accent(self) -> tuple:
        return self.colors["accent"]

    @property
    def text(self) -> tuple:
        return self.colors["text"]

    @property
    def text_secondary(self) -> tuple:
        return self.colors["text_secondary"]

    @property
    def overlay_alpha(self) -> int:
        return self.colors["overlay_alpha"]

    # ── Texture Overlays ──────────────────────────────────────────────────────

    def add_texture(self, image: Image.Image, texture_name: str = "grain",
                    opacity: int = 25) -> Image.Image:
        """
        Overlay a subtle texture (grain, paper, vignette) for depth.
        """
        texture = _get_texture(texture_name)
        if texture is None:
            return image

        # Resize texture to match image
        texture = texture.resize(image.size, Image.LANCZOS)

        # Adjust opacity
        if texture.mode == "RGBA":
            alpha = texture.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity / 255))
            texture.putalpha(alpha)
        else:
            texture = texture.convert("RGBA")
            texture.putalpha(opacity)

        # Composite
        result = image.convert("RGBA")
        result = Image.alpha_composite(result, texture)
        return result.convert("RGB")

    def add_vignette(self, image: Image.Image, strength: float = 0.4) -> Image.Image:
        """
        Add a subtle dark vignette to focus attention on center.
        """
        width, height = image.size
        vignette = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(vignette)

        # Create a radial gradient from center (white) to edges (dark)
        # We'll use a simple approximation: draw progressively larger dark rectangles
        steps = 40
        for i in range(steps):
            ratio = i / steps
            alpha = int(255 * strength * ratio)
            color = 255 - alpha
            inset = int(min(width, height) * ratio * 0.5)
            draw.rectangle(
                [inset, inset, width - inset, height - inset],
                outline=color,
            )
        # Fill center white
        center_inset = int(min(width, height) * 0.3)
        draw.rectangle(
            [center_inset, center_inset, width - center_inset, height - center_inset],
            fill=255,
        )

        # Blur the vignette for smoothness
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=min(width, height) // 15))

        # Apply as alpha
        result = image.copy()
        if result.mode != "RGBA":
            result = result.convert("RGBA")
        result.putalpha(vignette)
        return result.convert("RGB")

    # ── Layout Presets ────────────────────────────────────────────────────────

    def get_text_panel(self, image: Image.Image,
                       y_start: int, y_end: int,
                       blur_radius: int = 40) -> Image.Image:
        """
        Create a blurred/darkened panel behind text for readability.
        More sophisticated than a solid rectangle.
        """
        panel = image.copy().convert("RGBA")
        crop = panel.crop((0, y_start, image.width, y_end))

        # Blur the crop
        blurred = crop.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        # Darken it
        overlay = Image.new("RGBA", blurred.size, (*self.colors["primary"][:3], self.colors["overlay_alpha"]))
        darkened = Image.alpha_composite(blurred, overlay)

        # Paste back
        panel.paste(darkened, (0, y_start))
        return panel

    # ── Convenience: Create gradient text image ────────────────────────────────

    def create_gradient_text(self, text: str, font: ImageFont.FreeTypeFont,
                             width: int, height: int) -> Image.Image:
        """
        Render text with a vertical gradient from accent color to text color.
        """
        # Create mask from text
        mask = Image.new("L", (width, height), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.text((0, 0), text, font=font, fill=255)

        # Build gradient
        start = self.colors["gradient_start"]
        end = self.colors["gradient_end"]
        gradient = Image.new("RGB", (width, height))
        for y in range(height):
            ratio = y / max(height - 1, 1)
            r = int(start[0] * (1 - ratio) + end[0] * ratio)
            g = int(start[1] * (1 - ratio) + end[1] * ratio)
            b = int(start[2] * (1 - ratio) + end[2] * ratio)
            for x in range(width):
                gradient.putpixel((x, y), (r, g, b))

        # Composite through mask
        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        result.paste(gradient, (0, 0), mask)
        return result


# ── Module-level convenience functions ───────────────────────────────────────

def get_design(mood: str) -> BrandDesign:
    """Factory: return a BrandDesign instance for the given mood."""
    return BrandDesign(mood=mood)
