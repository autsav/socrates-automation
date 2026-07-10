"""
Instagram Story Generator — daily Story content, Pillow only (no FLUX).

Story types:
  - quote:    Quote of the day
  - question: Question of the day (engagement bait)
  - bts:      Behind-the-scenes text card
  - poll:     Poll-style prompt with two options (pair with IG's native
              poll sticker after posting — this renders the visual card)

Simple, bold, story-native design: full-bleed mood background, safe-zone
aware layout (top/bottom ~250px reserved for IG's UI chrome), large centered
text using the same font system as src.visual.brand_design.

Usage:
    from src.engagement.story_generator import StoryGenerator

    gen = StoryGenerator(mood="dark_philosophical")
    path = gen.generate_quote_story("The unexamined life is not worth living.")
    paths = gen.generate_daily_set(quote="...", question="...", bts_text="...")
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageDraw

from src.visual.brand_design import BrandDesign, calculate_font_size

STORY_SIZE = (1080, 1920)
SAFE_TOP = 250
SAFE_BOTTOM = 1670
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "stories"


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class StoryGenerator:
    """Generates 1080x1920 Instagram Story image cards."""

    def __init__(self, mood: str = "dark_philosophical", output_dir: str | Path = OUTPUT_DIR):
        self.mood = mood
        self.design = BrandDesign(mood=mood)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Shared canvas helpers ────────────────────────────────────────────

    def _base_canvas(self) -> Image.Image:
        """Solid mood-primary background — simple, bold, story-native."""
        return Image.new("RGB", STORY_SIZE, color=self.design.colors["primary"])

    def _draw_centered_text(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        text: str,
        y_center: int,
        base_size: int,
        color: tuple,
        weight: str = "bold",
        max_width_ratio: float = 0.84,
    ) -> int:
        """Draw word-wrapped, centered text around y_center. Returns block height."""
        max_width = int(STORY_SIZE[0] * max_width_ratio)
        size = calculate_font_size(text, base_size=base_size, min_size=36)
        font = self.design.get_font(size, weight=weight)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = int(size * 1.3)
        total_height = line_height * len(lines)
        y = y_center - total_height // 2
        for line in lines:
            width = draw.textlength(line, font=font)
            x = (STORY_SIZE[0] - width) / 2
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
            draw.text((x, y), line, font=font, fill=color)
            y += line_height
        return total_height

    def _save(self, image: Image.Image, name: str) -> Path:
        timestamp = str(int(time.time() * 1000))
        path = self.output_dir / f"{name}_{timestamp}.jpg"
        image.convert("RGB").save(path, quality=95)
        return path

    # ── Story types ──────────────────────────────────────────────────────

    def generate_quote_story(self, quote: str, author: str = "Socrates", output_path: str | Path | None = None) -> Path:
        """Quote-of-the-day Story card."""
        image = self._base_canvas()
        draw = ImageDraw.Draw(image)

        # Accent rule above the quote — simple, bold story-native motif.
        rule_y = SAFE_TOP + 120
        draw.rectangle(
            [STORY_SIZE[0] // 2 - 60, rule_y, STORY_SIZE[0] // 2 + 60, rule_y + 6],
            fill=self.design.colors["accent"],
        )

        self._draw_centered_text(
            draw, image, quote, y_center=STORY_SIZE[1] // 2 - 40,
            base_size=76, color=self.design.colors["text"],
        )
        self._draw_centered_text(
            draw, image, f"— {author}", y_center=SAFE_BOTTOM - 100,
            base_size=40, color=self.design.colors["accent"], weight="italic",
        )

        if output_path:
            path = Path(output_path)
            image.convert("RGB").save(path, quality=95)
            return path
        return self._save(image, "quote_story")

    def generate_question_story(self, question: str, output_path: str | Path | None = None) -> Path:
        """Question-of-the-day Story card (engagement bait — pair with IG's
        native Question sticker after posting)."""
        image = self._base_canvas()
        draw = ImageDraw.Draw(image)

        label = "QUESTION OF THE DAY"
        font = self.design.get_font(36, weight="bold")
        label_width = draw.textlength(label, font=font)
        draw.text(
            ((STORY_SIZE[0] - label_width) / 2, SAFE_TOP + 60),
            label, font=font, fill=self.design.colors["accent"],
        )

        self._draw_centered_text(
            draw, image, question, y_center=STORY_SIZE[1] // 2,
            base_size=72, color=self.design.colors["text"],
        )

        if output_path:
            path = Path(output_path)
            image.convert("RGB").save(path, quality=95)
            return path
        return self._save(image, "question_story")

    def generate_bts_story(self, caption: str, output_path: str | Path | None = None) -> Path:
        """Behind-the-scenes text card (process/personality content)."""
        image = self._base_canvas()
        draw = ImageDraw.Draw(image)

        label = "BEHIND THE SCENES"
        font = self.design.get_font(34, weight="bold")
        label_width = draw.textlength(label, font=font)
        draw.text(
            ((STORY_SIZE[0] - label_width) / 2, SAFE_TOP + 60),
            label, font=font, fill=self.design.colors["text_secondary"],
        )

        self._draw_centered_text(
            draw, image, caption, y_center=STORY_SIZE[1] // 2,
            base_size=58, color=self.design.colors["text"],
        )

        if output_path:
            path = Path(output_path)
            image.convert("RGB").save(path, quality=95)
            return path
        return self._save(image, "bts_story")

    def generate_poll_story(
        self,
        question: str,
        option_a: str = "Yes",
        option_b: str = "No",
        output_path: str | Path | None = None,
    ) -> Path:
        """Poll-prompt Story card — pair with Instagram's native poll
        sticker (option text mirrored here for the visual card)."""
        image = self._base_canvas()
        draw = ImageDraw.Draw(image)

        self._draw_centered_text(
            draw, image, question, y_center=SAFE_TOP + 350,
            base_size=64, color=self.design.colors["text"],
        )

        box_w, box_h = 420, 140
        gap = 40
        total_w = box_w * 2 + gap
        left_x = (STORY_SIZE[0] - total_w) // 2
        box_y = STORY_SIZE[1] // 2 + 150

        for i, label in enumerate((option_a, option_b)):
            x0 = left_x + i * (box_w + gap)
            x1 = x0 + box_w
            y1 = box_y + box_h
            draw.rounded_rectangle([x0, box_y, x1, y1], radius=24, outline=self.design.colors["accent"], width=4)
            font = self.design.get_font(44, weight="bold")
            text_width = draw.textlength(label, font=font)
            draw.text(
                (x0 + (box_w - text_width) / 2, box_y + (box_h - 44) / 2),
                label, font=font, fill=self.design.colors["text"],
            )

        if output_path:
            path = Path(output_path)
            image.convert("RGB").save(path, quality=95)
            return path
        return self._save(image, "poll_story")

    def generate_daily_set(
        self,
        quote: str,
        question: str,
        bts_text: str = "",
        author: str = "Socrates",
    ) -> list[Path]:
        """Generate the day's Story rotation: quote + question (+ optional BTS)."""
        paths = [
            self.generate_quote_story(quote, author=author),
            self.generate_question_story(question),
        ]
        if bts_text:
            paths.append(self.generate_bts_story(bts_text))
        return paths


# ── Convenience exports ──────────────────────────────────────────────────

def generate_story(
    story_type: str,
    mood: str = "dark_philosophical",
    output_dir: str | Path = OUTPUT_DIR,
    **kwargs,
) -> Path:
    """
    One-shot Story generation. story_type: quote | question | bts | poll.
    kwargs are forwarded to the matching StoryGenerator method.
    """
    gen = StoryGenerator(mood=mood, output_dir=output_dir)
    dispatch = {
        "quote": gen.generate_quote_story,
        "question": gen.generate_question_story,
        "bts": gen.generate_bts_story,
        "poll": gen.generate_poll_story,
    }
    if story_type not in dispatch:
        raise ValueError(f"Unknown story_type {story_type!r}. Use one of {list(dispatch)}.")
    return dispatch[story_type](**kwargs)
