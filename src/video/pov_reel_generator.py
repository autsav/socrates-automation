"""
POV Text Reel Generator — THE VIRAL ENGINE.

Generates the "POV text on dark background" Instagram Reel format that
actually goes viral for quote/philosophy accounts in 2026: black/dark
gradient background, large centered white text (hook -> quote -> CTA),
smooth fades, trending or ambient audio. Zero API cost — only ffmpeg +
Pillow. Uses the same font system as src.visual.brand_design.

Usage:
    from src.video.pov_reel_generator import generate_pov_reel, generate_pov_reels

    path = generate_pov_reel(
        quote="The unexamined life is not worth living.",
        hook="Socrates said something that will bother you all day.",
        cta="Save this before you forget it.",
        output_path="output/pov_reels/pov_1.mp4",
    )

    paths = generate_pov_reels(quotes=[{"quote": "...", "audience": "stuck"}, ...],
                                output_dir="output/pov_reels")
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageDraw

from src.visual.brand_design import BrandDesign, calculate_font_size

OUTPUT_SIZE = (1080, 1920)
DEFAULT_FPS = 30
MIN_TOTAL_DURATION = 7.0
MAX_TOTAL_DURATION = 15.0
FADE_DURATION = 0.35

# ── Zero-cost hook/CTA pools (used when a batch item doesn't supply its own) ──

_DEFAULT_HOOKS = [
    "POV: you finally read the quote that changes everything.",
    "Socrates said something that will bother you all day.",
    "Ancient wisdom. Modern problem. Same answer.",
    "Most people will scroll past this. Don't.",
    "This quote lives rent-free in my head.",
    "Read this before you scroll away.",
    "2,400 years old. Still the most relevant thing you'll read today.",
]

_DEFAULT_CTAS = [
    "Save this for the moment you need it.",
    "Send this to someone who needs to hear it.",
    "Follow for daily wisdom that hits different.",
    "Which line hit hardest? Comment below.",
    "Share this to your Story before you forget it.",
    "Screenshot the line that hurts most.",
]


def ffmpeg_available() -> bool:
    """Check if ffmpeg is installed and usable."""
    return shutil.which("ffmpeg") is not None


# ── Background ────────────────────────────────────────────────────────────

def _build_gradient_background(mood: str = "dark_philosophical", seed: int = 0) -> Image.Image:
    """Black/dark vertical gradient background, subtly tinted by mood.
    Near-black at top and bottom, a touch lighter (mood primary) in the middle
    so text always sits on a very dark, low-contrast field."""
    design = BrandDesign(mood=mood)
    primary = design.colors["primary"]
    width, height = OUTPUT_SIZE

    top = (0, 0, 0)
    bottom = (max(primary[0] - 5, 0), max(primary[1] - 5, 0), max(primary[2] - 5, 0))

    gradient = Image.new("RGB", (1, height), color=0)
    for y in range(height):
        # Peak brightness around the vertical center, fading to black at edges.
        ratio = 1 - abs((y / max(height - 1, 1)) - 0.5) * 2
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        gradient.putpixel((0, y), (r, g, b))
    gradient = gradient.resize((width, height))
    return gradient


# ── Text overlay rendering ───────────────────────────────────────────────

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Pixel-accurate word wrap using the given font."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textlength(candidate, font=font)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(
    text: str,
    base_size: int,
    min_size: int,
    max_width: int,
    max_height: int,
    design: BrandDesign,
    weight: str = "bold",
) -> tuple[list[str], object, int]:
    """Shrink font size until the wrapped text fits within max_width/max_height."""
    scratch = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(scratch)

    size = base_size
    while size >= min_size:
        font = design.get_font(size, weight=weight)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = int(size * 135 / 1000) + int(size * 0.35)
        total_height = line_height * len(lines)
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if total_height <= max_height and widest <= max_width:
            return lines, font, line_height
        size -= 4

    font = design.get_font(min_size, weight=weight)
    lines = _wrap_text(draw, text, font, max_width)
    line_height = int(min_size * 1.35)
    return lines, font, line_height


def render_text_overlay(
    text: str,
    mood: str = "dark_philosophical",
    base_size: int = 96,
    min_size: int = 40,
    weight: str = "bold",
    color: tuple = (250, 250, 248),
    shadow: bool = True,
) -> Image.Image:
    """
    Render large, centered, mobile-friendly white text on a transparent
    1080x1920 RGBA canvas, sized/wrapped to fit the safe area.
    """
    design = BrandDesign(mood=mood)
    width, height = OUTPUT_SIZE
    max_width = int(width * 0.86)
    max_height = int(height * 0.55)

    lines, font, line_height = _fit_text(
        text, base_size=base_size, min_size=min_size,
        max_width=max_width, max_height=max_height, design=design, weight=weight,
    )

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    total_height = line_height * len(lines)
    y = (height - total_height) // 2

    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 170))
        draw.text((x, y), line, font=font, fill=(*color, 255))
        y += line_height

    return overlay


def _quote_font_size(quote: str) -> int:
    """Reuse brand_design's dynamic sizing, scaled up for the POV full-bleed format."""
    return min(96, calculate_font_size(quote, base_size=104, min_size=44))


# ── Audio resolution ─────────────────────────────────────────────────────

def _resolve_audio(mood: str, audio_path: str | Path | None, output_dir: Path) -> Path | None:
    """
    Resolve background audio for the Reel, in priority order:
    explicit path -> trending hijacker -> cached/generated ambient -> silent.
    Never raises — audio is best-effort.
    """
    if audio_path:
        p = Path(audio_path)
        if p.exists():
            return p

    try:
        from src.audio.trending_hijacker import get_audio_for_mood
        track = get_audio_for_mood(mood)
        if track and Path(track).exists():
            return Path(track)
    except Exception:
        pass

    try:
        from src.audio.trending_audio import download_music_for_mood
        track = download_music_for_mood(mood)
        if track and Path(track).exists():
            return Path(track)
    except Exception:
        pass

    try:
        from generate_audio import prepare_reel_audio
        track = prepare_reel_audio(mood, target_duration=MAX_TOTAL_DURATION, output_dir=str(output_dir))
        if track and Path(track).exists():
            return Path(track)
    except Exception:
        pass

    return None


# ── Core generator ────────────────────────────────────────────────────────

def _clamp_durations(hook_duration: float, quote_duration: float, cta_duration: float) -> tuple[float, float, float]:
    total = hook_duration + quote_duration + cta_duration
    if total < MIN_TOTAL_DURATION:
        quote_duration += MIN_TOTAL_DURATION - total
    elif total > MAX_TOTAL_DURATION:
        scale = (MAX_TOTAL_DURATION - hook_duration - cta_duration) / max(quote_duration, 0.01)
        quote_duration = max(quote_duration * scale, 2.0)
    return hook_duration, quote_duration, cta_duration


def generate_pov_reel(
    quote: str,
    hook: str,
    cta: str,
    output_path: str | Path,
    mood: str = "dark_philosophical",
    hook_duration: float = 3.0,
    quote_duration: float | None = None,
    cta_duration: float = 2.0,
    fps: int = DEFAULT_FPS,
    seed: int = 0,
    animate_background: bool = True,
    audio_path: str | Path | None = None,
) -> Path | None:
    """
    Generate a single POV text Reel: black/dark gradient background,
    large centered white text fading hook (~3s) -> quote (~5-8s) -> CTA (~2s).
    1080x1920, 30fps, 7-15s total. ffmpeg + Pillow only — zero API cost.

    Returns the output path, or None if ffmpeg is unavailable.
    """
    if not ffmpeg_available():
        print("  [pov] ffmpeg not found — skipping POV Reel generation")
        return None

    if quote_duration is None:
        # 5-8s scaled with quote length.
        quote_duration = min(8.0, max(5.0, 5.0 + len(quote) / 90))

    hook_duration, quote_duration, cta_duration = _clamp_durations(
        hook_duration, quote_duration, cta_duration)
    total_duration = hook_duration + quote_duration + cta_duration

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_path.parent / f".pov_tmp_{output_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── Render frames ─────────────────────────────────────────────────
        bg = _build_gradient_background(mood=mood, seed=seed)
        bg_path = tmp_dir / "bg.png"
        bg.save(bg_path)

        hook_overlay = render_text_overlay(hook, mood=mood, base_size=88, min_size=40)
        quote_overlay = render_text_overlay(quote, mood=mood, base_size=_quote_font_size(quote), min_size=40)
        cta_overlay = render_text_overlay(cta, mood=mood, base_size=64, min_size=32)

        hook_path = tmp_dir / "hook.png"
        quote_path = tmp_dir / "quote.png"
        cta_path = tmp_dir / "cta.png"
        hook_overlay.save(hook_path)
        quote_overlay.save(quote_path)
        cta_overlay.save(cta_path)

        # ── Resolve audio (best-effort, never blocks) ───────────────────────
        audio = _resolve_audio(mood, audio_path, tmp_dir)

        # ── Build ffmpeg command ────────────────────────────────────────────
        hook_end = hook_duration
        quote_end = hook_duration + quote_duration

        cmd = ["ffmpeg", "-y"]
        cmd += ["-framerate", str(fps), "-loop", "1", "-t", str(total_duration), "-i", str(bg_path)]
        cmd += ["-framerate", str(fps), "-loop", "1", "-t", str(total_duration), "-i", str(hook_path)]
        cmd += ["-framerate", str(fps), "-loop", "1", "-t", str(total_duration), "-i", str(quote_path)]
        cmd += ["-framerate", str(fps), "-loop", "1", "-t", str(total_duration), "-i", str(cta_path)]

        if animate_background:
            bg_filter = (
                f"[0:v]zoompan=z='min(zoom+0.0008,1.06)':d=1:"
                f"s={OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}:fps={fps}[bgv]"
            )
        else:
            bg_filter = "[0:v]format=yuv420p[bgv]"

        hook_fade = (
            f"[1:v]fade=t=in:st=0:d={FADE_DURATION}:alpha=1,"
            f"fade=t=out:st={max(hook_end - FADE_DURATION, 0):.3f}:d={FADE_DURATION}:alpha=1[htxt]"
        )
        quote_fade = (
            f"[2:v]fade=t=in:st={hook_end:.3f}:d={FADE_DURATION}:alpha=1,"
            f"fade=t=out:st={max(quote_end - FADE_DURATION, 0):.3f}:d={FADE_DURATION}:alpha=1[qtxt]"
        )
        cta_fade = (
            f"[3:v]fade=t=in:st={quote_end:.3f}:d={FADE_DURATION}:alpha=1,"
            f"fade=t=out:st={max(total_duration - FADE_DURATION, 0):.3f}:d={FADE_DURATION}:alpha=1[ctxt]"
        )

        overlay_hook = f"[bgv][htxt]overlay=0:0:enable='between(t,0,{hook_end:.3f})'[v1]"
        overlay_quote = f"[v1][qtxt]overlay=0:0:enable='between(t,{hook_end:.3f},{quote_end:.3f})'[v2]"
        overlay_cta = (
            f"[v2][ctxt]overlay=0:0:enable='between(t,{quote_end:.3f},{total_duration:.3f})',"
            f"format=yuv420p[outv]"
        )

        filter_complex = ";".join([
            bg_filter, hook_fade, quote_fade, cta_fade,
            overlay_hook, overlay_quote, overlay_cta,
        ])

        cmd += ["-filter_complex", filter_complex, "-map", "[outv]"]

        if audio is not None:
            cmd += ["-i", str(audio)]
            audio_idx = 4
            cmd += [
                "-map", f"{audio_idx}:a",
                "-c:a", "aac", "-b:a", "128k",
                "-af", f"afade=t=in:d=0.4,afade=t=out:st={max(total_duration - 0.6, 0):.3f}:d=0.6",
                "-shortest",
            ]
        else:
            cmd += ["-an"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-t", str(total_duration),
            str(output_path),
        ]

        print(f"  [pov] Generating POV Reel ({total_duration:.1f}s)...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            error = result.stderr[-600:] if result.stderr else "unknown error"
            raise RuntimeError(f"ffmpeg POV reel generation failed: {error}")

        size = output_path.stat().st_size
        print(f"  [pov] Saved: {output_path} ({size / 1024:.0f} KB)")
        return output_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def generate_pov_reels(
    quotes: list,
    output_dir: str | Path,
    mood_map: dict | None = None,
) -> list:
    """
    Batch-generate POV Reels for a list of quotes.

    Each item in `quotes` may be a plain string (the quote text) or a dict
    with keys: quote (required), hook, cta, mood, audience, row_number.
    Missing hook/cta/mood are filled from the zero-cost default pools.

    Returns the list of successfully generated output paths (skips failures).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mood_map = mood_map or {}

    results = []
    for i, item in enumerate(quotes):
        if isinstance(item, str):
            item = {"quote": item}

        quote_text = item.get("quote", "")
        if not quote_text:
            continue

        hook = item.get("hook") or _DEFAULT_HOOKS[i % len(_DEFAULT_HOOKS)]
        cta = item.get("cta") or _DEFAULT_CTAS[i % len(_DEFAULT_CTAS)]
        mood = item.get("mood") or mood_map.get(item.get("audience", ""), "dark_philosophical")
        row_number = item.get("row_number", i)

        timestamp = str(int(time.time() * 1000))
        output_path = output_dir / f"pov_reel_{row_number}_{timestamp}.mp4"

        try:
            path = generate_pov_reel(
                quote=quote_text,
                hook=hook,
                cta=cta,
                output_path=output_path,
                mood=mood,
                seed=i,
            )
            if path:
                results.append(path)
        except Exception as e:
            print(f"  [pov] ⚠️ Failed to generate Reel for row {row_number}: {e}")

    print(f"  [pov] Batch complete: {len(results)}/{len(quotes)} POV Reels generated → {output_dir}")
    return results


if __name__ == "__main__":
    out = generate_pov_reel(
        quote="The unexamined life is not worth living.",
        hook="Socrates said something that will bother you all day.",
        cta="Save this before you forget it.",
        output_path="output/pov_reels/pov_demo.mp4",
    )
    print(out)
