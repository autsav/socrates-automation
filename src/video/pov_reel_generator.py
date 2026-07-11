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

# Per-mood glow color for the radial background. Kept dark enough that huge
# white text stays high-contrast; the animated ffmpeg filters make it pulse,
# shift, and brighten so the field never sits still.
_PULSE_COLORS = {
    "dark_philosophical": (82, 16, 16),   # deep blood red
    "dramatic_ancient":   (86, 36, 14),   # ember orange
    "cinematic_hopeful":  (14, 36, 86),   # electric blue
    "stark_minimal":      (58, 58, 64),   # cold slate
    "epic_warrior":       (96, 14, 14),   # war red
    "mystical_greek":     (48, 16, 88),   # violet
    "calm_stoic":         (16, 54, 36),   # forest
}


def _build_gradient_background(mood: str = "dark_philosophical", seed: int = 0) -> Image.Image:
    """Radial glow background: a saturated mood-colored core fading to near-black
    at the edges. Text sits on the dark rim's high-contrast field while the
    animated filter chain makes the core breathe, shift hue, and pulse — the
    background creates tension, the text delivers release."""
    width, height = OUTPUT_SIZE
    core = _PULSE_COLORS.get(mood, _PULSE_COLORS["dark_philosophical"])
    edge = (0, 0, 0)

    # Compute the radial falloff at low resolution, then upscale smoothly —
    # a full 2M-pixel Python loop would be far too slow.
    lw, lh = max(width // 6, 1), max(height // 6, 1)
    small = Image.new("RGB", (lw, lh))
    px = small.load()
    cx, cy = (lw - 1) / 2, (lh - 1) / 2
    max_d = (cx ** 2 + cy ** 2) ** 0.5 or 1.0
    for y in range(lh):
        for x in range(lw):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / max_d
            t = min(1.0, d ** 1.4)  # broad glow in the center, dark toward the rim
            r = int(core[0] * (1 - t) + edge[0] * t)
            g = int(core[1] * (1 - t) + edge[1] * t)
            b = int(core[2] * (1 - t) + edge[2] * t)
            px[x, y] = (r, g, b)
    return small.resize((width, height), Image.LANCZOS)


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

    def _line_height(font) -> int:
        # Derive from real font metrics (ascent + descent) so big glyphs never
        # collide; a flat fraction of `size` badly under-spaces large fonts.
        try:
            ascent, descent = font.getmetrics()
            return int((ascent + descent) * 1.12)
        except Exception:
            return int(getattr(font, "size", 40) * 1.25)

    size = base_size
    while size >= min_size:
        font = design.get_font(size, weight=weight)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = _line_height(font)
        total_height = line_height * len(lines)
        widest = max((draw.textlength(line, font=font) for line in lines), default=0)
        if total_height <= max_height and widest <= max_width:
            return lines, font, line_height
        size -= 4

    font = design.get_font(min_size, weight=weight)
    lines = _wrap_text(draw, text, font, max_width)
    return lines, font, _line_height(font)


def render_text_overlay(
    text: str,
    mood: str = "dark_philosophical",
    base_size: int = 160,
    min_size: int = 92,
    weight: str = "bold",
    color: tuple = (255, 255, 255),
    shadow: bool = True,
) -> Image.Image:
    """
    Render HUGE, centered, mobile-first white text on a transparent 1080x1920
    RGBA canvas — the text is the content, so it dominates the frame, filling
    ~90% of the width and wrapping full-bleed lines. A heavy black stroke plus
    drop shadow keep it razor-legible over the moving, pulsing background.
    """
    design = BrandDesign(mood=mood)
    width, height = OUTPUT_SIZE
    max_width = int(width * 0.90)
    max_height = int(height * 0.70)

    lines, font, line_height = _fit_text(
        text, base_size=base_size, min_size=min_size,
        max_width=max_width, max_height=max_height, design=design, weight=weight,
    )

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Stroke scales with font size so big text gets a proportionally bold outline.
    size = getattr(font, "size", base_size)
    stroke_width = max(4, int(size * 0.055))
    shadow_offset = max(4, int(size * 0.045))

    total_height = line_height * len(lines)
    y = (height - total_height) // 2

    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        if shadow:
            draw.text(
                (x + shadow_offset, y + shadow_offset), line, font=font,
                fill=(0, 0, 0, 180), stroke_width=stroke_width, stroke_fill=(0, 0, 0, 180),
            )
        draw.text(
            (x, y), line, font=font, fill=(*color, 255),
            stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255),
        )
        y += line_height

    return overlay


def _quote_font_size(quote: str) -> int:
    """Reuse brand_design's dynamic sizing, scaled up huge for the POV full-bleed format."""
    return min(150, calculate_font_size(quote, base_size=172, min_size=100))


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

        hook_overlay = render_text_overlay(hook, mood=mood, base_size=168, min_size=100)
        quote_overlay = render_text_overlay(quote, mood=mood, base_size=_quote_font_size(quote), min_size=96)
        cta_overlay = render_text_overlay(cta, mood=mood, base_size=132, min_size=84)

        hook_path = tmp_dir / "hook.png"
        quote_path = tmp_dir / "quote.png"
        cta_path = tmp_dir / "cta.png"
        hook_overlay.save(hook_path)
        quote_overlay.save(quote_path)
        cta_overlay.save(cta_path)

        # White flash frame for the pattern-interrupt flashes at scene transitions.
        flash_frame = Image.new("RGBA", OUTPUT_SIZE, (255, 255, 255, 210))
        flash_path = tmp_dir / "flash.png"
        flash_frame.save(flash_path)

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

        next_idx = 4
        flash_idx = None
        if animate_background:
            cmd += ["-framerate", str(fps), "-loop", "1", "-t", str(total_duration), "-i", str(flash_path)]
            flash_idx = next_idx
            next_idx += 1

        if audio is not None:
            cmd += ["-i", str(audio)]
            audio_idx = next_idx
            next_idx += 1

        sw, sh = OUTPUT_SIZE
        if animate_background:
            # ALIVE + UNSTABLE background: slow zoom, moving film grain, a color
            # pulse (dark ↔ lighter every ~1.5s), a slow hue shift, a breathing
            # vignette that darkens/releases the edges toward the center text,
            # and a 2-3px shake for urgency. All zero-cost ffmpeg filters.
            margin = 12
            half = margin // 2
            bg_filter = (
                f"[0:v]zoompan=z='min(zoom+0.0006,1.08)':d=1:s={sw}x{sh}:fps={fps},"
                f"scale={sw + margin}:{sh + margin},"
                f"noise=alls=14:allf=t+u,"
                f"eq=brightness='0.05+0.06*sin(2*PI*t/1.5)':"
                f"saturation='1.18+0.18*sin(2*PI*t/2)':eval=frame,"
                f"hue=h='12*sin(2*PI*t/3)',"
                f"vignette=a='PI/4.5+0.10*sin(2*PI*t/2)':eval=frame,"
                f"crop={sw}:{sh}:"
                f"x='{half}+3*sin(2*PI*t*4)+2*sin(2*PI*t*7)':"
                f"y='{half}+3*cos(2*PI*t*5)+2*sin(2*PI*t*9)',"
                f"format=yuv420p[bgv]"
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

        filter_parts = [bg_filter, hook_fade, quote_fade, cta_fade,
                        overlay_hook, overlay_quote]

        if flash_idx is not None:
            # Text over background, then a brief hard white flash at each scene
            # transition (~0.08s) — a pattern interrupt that resets attention.
            overlay_cta = (
                f"[v2][ctxt]overlay=0:0:enable='between(t,{quote_end:.3f},{total_duration:.3f})'[v3]"
            )
            flash_overlay = (
                f"[v3][{flash_idx}:v]overlay=0:0:"
                f"enable='between(t,{max(hook_end - 0.04, 0):.3f},{hook_end + 0.04:.3f})"
                f"+between(t,{max(quote_end - 0.04, 0):.3f},{quote_end + 0.04:.3f})',"
                f"format=yuv420p[outv]"
            )
            filter_parts += [overlay_cta, flash_overlay]
        else:
            overlay_cta = (
                f"[v2][ctxt]overlay=0:0:enable='between(t,{quote_end:.3f},{total_duration:.3f})',"
                f"format=yuv420p[outv]"
            )
            filter_parts.append(overlay_cta)

        filter_complex = ";".join(filter_parts)

        cmd += ["-filter_complex", filter_complex, "-map", "[outv]"]

        if audio is not None:
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
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
