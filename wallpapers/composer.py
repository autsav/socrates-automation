"""
Wallpaper Series Composer — high-resolution save-bait content.

Creates square (1080×1080) and vertical (1080×1920) wallpapers
from Socrates quotes designed specifically for saves, shares, and
DMS ("send this to someone who needs it").

Psychology:
  - Aesthetic first → saves happen before reading
  - Minimal text → easier to consume
  - Brand watermark → attribution on reshares
  - Phone-optimized sizing → perfect for lock screens

Usage:
    from wallpapers.composer import WallpaperComposer
    wp = WallpaperComposer(mood="calm_stoic")
    paths = wp.create_wallpaper_set(quote, output_dir="output")
"""

import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from brand_design import BrandDesign, get_design


class WallpaperComposer:
    """
    Generate wallpaper-style images optimized for saves and shares.
    """

    SIZES = {
        "vertical": (1080, 1920),   # Instagram Reel / Story / Lock screen
        "square": (1080, 1080),      # Feed post / Pinterest
        "wide": (1920, 1080),        # Twitter/X header / desktop
    }

    # Quote categories that perform well as wallpapers
    WALLPAPER_CATEGORIES = [
        "discipline", "focus", "resilience", "patience",
        "courage", "wisdom", "simplicity", "endurance",
    ]

    # Subtle background enhancement keywords (prepended to image prompt)
    WALLPAPER_MOOD_ENHANCEMENTS = {
        "dark_philosophical": "soft bokeh, cinematic depth of field, film grain texture",
        "dramatic_ancient": "warm golden hour glow, dust particles in light rays",
        "cinematic_hopeful": "ethereal mist, sun rays through clouds, uplifting atmosphere",
        "stark_minimal": "clean negative space, subtle paper texture, precise shadows",
        "epic_warrior": "dramatic cloudscape, heroic scale, god rays",
        "mystical_greek": "bioluminescent accents, starlight, magical particles",
        "calm_stoic": "soft morning light, gentle fog, peaceful garden atmosphere",
    }

    def __init__(self, mood: str = "calm_stoic"):
        self.mood = mood
        self.design = get_design(mood)

    # ── Public API ─────────────────────────────────────────────────────────

    def create_wallpaper_set(self, quote: str, author: str = "Socrates",
                              output_dir: str = "output",
                              background_image: Image.Image | None = None,
                              seed: int = 0) -> dict[str, Path]:
        """
        Generate a full wallpaper set from one quote.
        Returns dict of format -> output path.
        """
        if seed:
            random.seed(seed)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for fmt, size in self.SIZES.items():
            # Generate or resize background
            if background_image is not None:
                bg = background_image.copy()
                bg = self._crop_to_size(bg, size)
            else:
                bg = self._generate_solid_background(size)

            # Compose wallpaper
            wallpaper = self._compose_wallpaper(bg, quote, author, size)

            # Save
            path = output_dir / f"wallpaper_{fmt}_{self.mood}_{seed or random.randint(1000,9999)}.jpg"
            wallpaper.save(path, quality=95, optimize=True)
            results[fmt] = path
            print(f"  [wallpaper] Created {fmt}: {path.name}")

        return results

    def create_lock_screen(self, quote: str, output_dir: str = "output",
                           background_image: Image.Image | None = None,
                           seed: int = 0) -> Path:
        """Create a phone lock screen optimized wallpaper."""
        size = self.SIZES["vertical"]

        if background_image is not None:
            bg = background_image.copy()
            bg = self._crop_to_size(bg, size)
        else:
            bg = self._generate_solid_background(size)

        # Lock screens need the time area (top 20%) and swipe area (bottom 15%) kept clear
        wallpaper = self._compose_wallpaper(
            bg, quote, "Socrates", size,
            safe_top=int(size[1] * 0.22),
            safe_bottom=int(size[1] * 0.85),
        )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"lockscreen_{self.mood}_{seed or random.randint(1000,9999)}.jpg"
        wallpaper.save(path, quality=95, optimize=True)
        return path

    def enhance_image_prompt(self, base_prompt: str) -> str:
        """Add wallpaper-specific visual enhancements to an image prompt."""
        enhancement = self.WALLPAPER_MOOD_ENHANCEMENTS.get(
            self.mood, self.WALLPAPER_MOOD_ENHANCEMENTS["calm_stoic"]
        )
        return f"{base_prompt}, {enhancement}, ultra high resolution, 8k detail"

    # ── Internal Composition ─────────────────────────────────────────────────

    def _compose_wallpaper(self, background: Image.Image, quote: str,
                           author: str, size: tuple,
                           safe_top: int = None, safe_bottom: int = None) -> Image.Image:
        """
        Compose a single wallpaper image.
        Minimal, aesthetic, designed for saves.
        """
        width, height = size
        safe_top = safe_top or int(height * 0.15)
        safe_bottom = safe_bottom or int(height * 0.90)

        img = background.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Add subtle vignette
        img = self.design.add_vignette(img, strength=0.35)
        draw = ImageDraw.Draw(img)

        # Calculate font sizes based on quote length
        quote_len = len(quote)
        if quote_len <= 80:
            font_size = 72
            author_size = 36
            line_max = 22
        elif quote_len <= 150:
            font_size = 58
            author_size = 30
            line_max = 26
        else:
            font_size = 48
            author_size = 28
            line_max = 30

        font = self.design.get_font(font_size, weight="bold")
        author_font = self.design.get_font(author_size, weight="regular")

        # Wrap quote
        lines = self._wrap_text(quote, line_max)

        # Calculate vertical center within safe zone
        bbox = draw.textbbox((0, 0), "Mg", font=font)
        line_h = bbox[3] - bbox[1] + 20
        total_h = len(lines) * line_h + 60  # +60 for author spacing
        y_start = safe_top + (safe_bottom - safe_top - total_h) // 2

        # Draw quote centered
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (width - text_w) // 2
            y = y_start + i * line_h

            # Subtle shadow
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 120))
            # Main text
            draw.text((x, y), line, font=font, fill=(*self.design.text[:3], 255))

        # Author attribution
        author_text = f"— {author}"
        bbox = draw.textbbox((0, 0), author_text, font=author_font)
        auth_w = bbox[2] - bbox[0]
        auth_x = (width - auth_w) // 2
        auth_y = y_start + len(lines) * line_h + 30

        # Accent line above author
        line_w = min(200, auth_w + 40)
        line_x = (width - line_w) // 2
        draw.line(
            [(line_x, auth_y - 15), (line_x + line_w, auth_y - 15)],
            fill=(*self.design.accent[:3], 180),
            width=2,
        )

        draw.text((auth_x + 1, auth_y + 1), author_text, font=author_font, fill=(0, 0, 0, 100))
        draw.text((auth_x, auth_y), author_text, font=author_font, fill=(*self.design.accent[:3], 255))

        # Brand watermark (bottom right, subtle)
        watermark_font = self.design.get_font(20, weight="regular")
        watermark = "@socrates.daily"
        wm_bbox = draw.textbbox((0, 0), watermark, font=watermark_font)
        wm_w = wm_bbox[2] - wm_bbox[0]
        draw.text(
            (width - wm_w - 30, height - 50),
            watermark,
            font=watermark_font,
            fill=(*self.design.text_secondary[:3], 120),
        )

        return img.convert("RGB")

    def _wrap_text(self, text: str, max_chars: int) -> list[str]:
        """Wrap text into balanced lines."""
        words = text.split()
        lines = []
        current = []
        current_len = 0

        for word in words:
            if current_len + len(word) + len(current) > max_chars and current:
                lines.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += len(word)

        if current:
            lines.append(" ".join(current))

        return lines

    def _crop_to_size(self, image: Image.Image, target_size: tuple) -> Image.Image:
        """Crop and resize an image to target size while maintaining aspect ratio."""
        target_w, target_h = target_size
        img_w, img_h = image.size

        # Calculate scale to fill target
        scale_w = target_w / img_w
        scale_h = target_h / img_h
        scale = max(scale_w, scale_h)

        new_w = int(img_w * scale)
        new_h = int(img_h * scale)

        resized = image.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        cropped = resized.crop((left, top, left + target_w, top + target_h))

        return cropped

    def _generate_solid_background(self, size: tuple) -> Image.Image:
        """Create a subtle gradient background as fallback."""
        width, height = size
        img = Image.new("RGB", size, self.design.primary)
        draw = ImageDraw.Draw(img)

        # Subtle radial gradient from center
        center = (width // 2, height // 2)
        max_dist = ((width // 2) ** 2 + (height // 2) ** 2) ** 0.5

        # Draw concentric rectangles (faster than per-pixel)
        steps = 60
        for i in range(steps):
            ratio = i / steps
            # Blend from primary to a slightly lighter version
            r = int(self.design.primary[0] + (self.design.secondary[0] - self.design.primary[0]) * ratio * 0.5)
            g = int(self.design.primary[1] + (self.design.secondary[1] - self.design.primary[1]) * ratio * 0.5)
            b = int(self.design.primary[2] + (self.design.secondary[2] - self.design.primary[2]) * ratio * 0.5)

            inset = int(max_dist * ratio * 0.7)
            draw.rectangle(
                [center[0] - inset, center[1] - inset,
                 center[0] + inset, center[1] + inset],
                outline=(r, g, b),
            )

        # Add noise for texture
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        return img


# ── Convenience exports ────────────────────────────────────────────────────────

def create_wallpaper(quote: str, mood: str = "calm_stoic",
                      output_dir: str = "output",
                      background_image: Image.Image | None = None) -> dict[str, Path]:
    """One-shot wallpaper creation."""
    composer = WallpaperComposer(mood=mood)
    return composer.create_wallpaper_set(
        quote=quote, output_dir=output_dir,
        background_image=background_image,
    )
