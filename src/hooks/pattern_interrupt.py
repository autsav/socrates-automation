"""
Pattern Interrupt Hooks — scroll-stopping visual effects for Reel Scene 1.

Implements viral content psychology:
  - Fake notification overlays (triggers FOMO/curiosity)
  - Color inversion flash (breaks scrolling autopilot)
  - Zoom burst (creates visual momentum)
  - Glitch frame (triggers micro-surprise)

Usage:
    from src.hooks.pattern_interrupt import PatternInterrupter
    hook = PatternInterrupter(mode="notification")
    result = hook.apply(scene_img, text="Someone liked your post")
"""

import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class PatternInterrupter:
    """Apply scroll-stopping visual effects to hook scenes."""

    # Brand colors for flash effects
    FLASH_COLORS = [
        (255, 80, 80),    # Alert red
        (255, 215, 0),    # Gold
        (0, 200, 255),    # Cyan (attention-grabbing on warm backgrounds)
        (255, 140, 0),    # Orange
        (255, 255, 255),  # White flash
    ]

    # Fake notification templates (psychology: FOMO + identity validation)
    NOTIFICATION_TEMPLATES = [
        "New follower: Someone who needed this",
        "3 people shared this",
        "Your post reached 10K people",
        "Someone saved this for later",
        "This hit different for 247 people",
        "Your words just changed someone's day",
    ]

    def __init__(self, mode: str = "notification"):
        """
        Args:
            mode: One of "notification", "color_flash", "zoom_burst", "glitch", "mixed"
        """
        self.mode = mode
        self.size = (1080, 1920)

    # ── Public API ─────────────────────────────────────────────────────────────

    def apply(self, image: Image.Image, text: str = "", seed: int = 0) -> Image.Image:
        """Apply the configured pattern interrupt to an image."""
        if seed:
            random.seed(seed)

        if self.mode == "notification":
            return self._add_fake_notification(image, text)
        elif self.mode == "color_flash":
            return self._add_color_flash(image)
        elif self.mode == "zoom_burst":
            return self._add_zoom_burst(image, text)
        elif self.mode == "glitch":
            return self._add_glitch(image)
        elif self.mode == "mixed":
            return self._add_mixed(image, text)
        return image

    @classmethod
    def random_mode(cls, seed: int = 0) -> str:
        """Return a random interrupt mode weighted by viral effectiveness."""
        if seed:
            random.seed(seed)
        # Weighted: notification highest-performing, then zoom, flash, glitch
        return random.choices(
            ["notification", "zoom_burst", "color_flash", "glitch", "mixed"],
            weights=[40, 25, 20, 10, 5],
            k=1,
        )[0]

    # ── Individual Effects ─────────────────────────────────────────────────────

    def _add_fake_notification(self, image: Image.Image, text: str = "") -> Image.Image:
        """
        Overlay a fake iOS/Android-style notification at the top.
        Triggers FOMO and makes viewer pause to check if it's real.
        """
        img = image.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Notification dimensions
        notif_h = 120
        padding_x = 30
        padding_y = 25
        y_pos = 80  # Below status bar area

        # Choose text
        notif_text = text or random.choice(self.NOTIFICATION_TEMPLATES)
        notif_title = "Instagram"
        notif_sub = notif_text

        # Draw notification background (dark translucent iOS style)
        notif_bg = Image.new("RGBA", (self.size[0] - 2 * padding_x, notif_h), (20, 20, 20, 230))
        # Rounded corners via mask
        mask = Image.new("L", notif_bg.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [0, 0, notif_bg.width - 1, notif_bg.height - 1],
            radius=25,
            fill=255
        )
        notif_bg.putalpha(mask)

        # Paste notification onto image
        img.paste(notif_bg, (padding_x, y_pos), notif_bg)

        # Load small font
        font_small = self._load_font(24)
        font_body = self._load_font(28)

        # Draw app name (bold-ish)
        draw.text(
            (padding_x + 25, y_pos + padding_y),
            notif_title,
            font=font_small,
            fill=(150, 150, 150),
        )

        # Draw notification body
        draw.text(
            (padding_x + 25, y_pos + padding_y + 38),
            notif_sub[:55] + ("..." if len(notif_sub) > 55 else ""),
            font=font_body,
            fill=(255, 255, 255),
        )

        # Add a tiny red dot (unread indicator)
        draw.ellipse(
            [padding_x + 8, y_pos + padding_y + 8, padding_x + 16, y_pos + padding_y + 16],
            fill=(255, 59, 48),
        )

        return img.convert("RGB")

    def _add_color_flash(self, image: Image.Image) -> Image.Image:
        """
        Invert colors in a top band + overlay a bright accent stripe.
        Forces the eye to stop due to chromatic disruption.
        """
        img = image.copy().convert("RGB")
        width, height = img.size

        # Flash zone: top 25% of image
        flash_h = int(height * 0.25)
        flash_color = random.choice(self.FLASH_COLORS)

        # Create semi-transparent flash overlay
        flash = Image.new("RGB", (width, flash_h), flash_color)
        flash = flash.convert("RGBA")
        flash.putalpha(90)  # 35% opacity

        # Composite
        img_rgba = img.convert("RGBA")
        img_rgba.paste(flash, (0, 0), flash)

        # Add bold text in the flash zone
        draw = ImageDraw.Draw(img_rgba)
        font = self._load_font(56, bold=True)

        flash_texts = [
            "WAIT.",
            "STOP SCROLLING.",
            "THIS ONE HITS.",
            "READ THIS.",
            "3 SECONDS.",
        ]
        text = random.choice(flash_texts)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        y = flash_h // 2 - 40

        # Stroke
        for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        return img_rgba.convert("RGB")

    def _add_zoom_burst(self, image: Image.Image, text: str = "") -> Image.Image:
        """
        Create a radial zoom blur effect emanating from center.
        Suggests motion and momentum — the video is 'already moving'.
        """
        img = image.copy().convert("RGB")
        width, height = img.size

        # Pre-zoom the image slightly
        zoomed = img.resize((int(width * 1.15), int(height * 1.15)), Image.LANCZOS)
        # Crop back to original size (centered)
        left = (zoomed.width - width) // 2
        top = (zoomed.height - height) // 2
        zoomed = zoomed.crop((left, top, left + width, top + height))

        # Radial blur simulation: scale down + overlay multiple times
        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for i, scale in enumerate([1.0, 0.97, 0.94, 0.91, 0.88]):
            scaled = zoomed.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
            s_left = (width - scaled.width) // 2
            s_top = (height - scaled.height) // 2
            layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            layer.paste(scaled, (s_left, s_top))
            # Fade out outer layers
            alpha = int(255 * (1 - i * 0.15))
            layer.putalpha(alpha)
            result = Image.alpha_composite(result, layer)

        # Overlay center text
        draw = ImageDraw.Draw(result)
        font = self._load_font(48, bold=True)
        center_text = text[:30] if text else random.choice([
            "IT'S TIME.",
            "THIS IS IT.",
            "PAY ATTENTION.",
        ])
        bbox = draw.textbbox((0, 0), center_text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        y = height // 2 - 30

        # Heavy stroke for readability
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), center_text, font=font, fill=(0, 0, 0, 200))
        draw.text((x, y), center_text, font=font, fill=(255, 255, 255, 255))

        return result.convert("RGB")

    def _add_glitch(self, image: Image.Image) -> Image.Image:
        """
        RGB channel split glitch effect.
        Signals 'something is broken / different' — forces attention.
        """
        img = image.copy().convert("RGB")
        width, height = img.size
        r, g, b = img.split()

        # Offset red channel slightly left
        r_offset = ImageChops.offset(r, random.randint(8, 20), 0)
        # Offset blue channel slightly right
        b_offset = ImageChops.offset(b, -random.randint(8, 20), 0)

        glitched = Image.merge("RGB", (r_offset, g, b_offset))

        # Add horizontal scanline slices
        draw = ImageDraw.Draw(glitched)
        for _ in range(random.randint(3, 6)):
            y = random.randint(100, height - 100)
            h = random.randint(2, 8)
            color = random.choice([(255, 255, 255), (0, 0, 0), (255, 0, 0), (0, 255, 255)])
            draw.rectangle([0, y, width, y + h], fill=color)

        return glitched

    def _add_mixed(self, image: Image.Image, text: str = "") -> Image.Image:
        """Combine notification + subtle color flash for maximum impact."""
        img = self._add_color_flash(image)
        return self._add_fake_notification(img, text)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Load a system font or fallback."""
        candidates = []
        if bold:
            candidates = [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        else:
            candidates = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        for path in candidates:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()


# Make ImageChops available for glitch
from PIL import ImageChops


# ── Point 22: Myth-Busting Hook Templates ────────────────────────────────────

MYTH_BUSTING_HOOKS: list[str] = [
    "Everything you think you know about discipline is wrong.",
    "Socrates didn't actually say 'Know thyself' — here's what he said.",
    "The self-help industry lied to you about motivation.",
    "Aristotle's actual advice would get him cancelled today.",
    "The ancient Greeks would think your life is incredibly small.",
    "What they don't teach you about stoicism in school.",
    "You've been misquoting Socrates your entire life.",
    "The real meaning of 'Know thyself' — it's not what you think.",
    "Ancient philosophers were brutal. Here's why that matters.",
    "Most 'stoic' content online completely misses the point.",
]


def get_myth_busting_hook(seed: int = 0) -> str:
    """
    Point 22: Return a myth-busting hook line.
    Controversy-format that forces engagement by challenging assumptions.
    """
    import random as _random
    if seed:
        _random.seed(seed)
    return _random.choice(MYTH_BUSTING_HOOKS)


# ── Point 25: "What Would X Say" Format Templates ────────────────────────────

WWXS_SCENARIOS: list[dict] = [
    {
        "philosopher": "Marcus Aurelius",
        "scenario": "your 2am doomscroll",
        "template": "What would Marcus Aurelius say about your 2am doomscroll?",
    },
    {
        "philosopher": "Socrates",
        "scenario": "Instagram",
        "template": "What would Socrates say if you showed him your Instagram feed?",
    },
    {
        "philosopher": "Epictetus",
        "scenario": "complaining about your job",
        "template": "What would Epictetus say about you complaining about your job?",
    },
    {
        "philosopher": "Seneca",
        "scenario": "wasting your Sunday",
        "template": "What would Seneca say about how you spent your Sunday?",
    },
    {
        "philosopher": "Plato",
        "scenario": "your opinion of your own potential",
        "template": "What would Plato say about how little you think of yourself?",
    },
    {
        "philosopher": "Diogenes",
        "scenario": "your morning routine",
        "template": "What would Diogenes say about your morning routine?",
    },
]


def get_wwxs_hook(philosopher: str = "", seed: int = 0) -> str:
    """
    Point 25: Return a 'What Would X Say' scenario hook.
    Bridges ancient wisdom + modern relatable situation.
    """
    import random as _random
    if seed:
        _random.seed(seed)

    if philosopher:
        matching = [s for s in WWXS_SCENARIOS if philosopher.lower() in s["philosopher"].lower()]
        if matching:
            return _random.choice(matching)["template"]

    return _random.choice(WWXS_SCENARIOS)["template"]
