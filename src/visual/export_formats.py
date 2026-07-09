"""
Multi-platform export formats for the Socrates pipeline.

Point 50: Content A/B variant generation
Point 51: TikTok cross-post format (9:16, 60fps target, native caption)
Point 52: YouTube Shorts export (16:9→9:16 crop, 1080×1920, metadata)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

Platform = Literal["instagram", "tiktok", "youtube_shorts"]

# ── Point 50: A/B Variant Generation ─────────────────────────────────────────


def generate_caption_variants(
    quote: str,
    hook_text: str,
    philosopher: str = "Socrates",
    seed: int = 0,
) -> dict[str, str]:
    """
    Point 50: Generate A/B caption variants for a post.
    Returns dict: {variant_a: caption, variant_b: caption}

    Variant A: Hook → Quote → CTA (question)
    Variant B: Quote → Context → CTA (statement)
    """
    import random
    random.seed(seed)

    cta_questions = [
        "Which part resonates most?",
        "What would you add?",
        "Does this change how you see your day?",
        "Save this — you'll need it.",
        "Who needs to see this today?",
    ]
    cta_statements = [
        "Follow for daily philosophy.",
        "Save this for the hard days.",
        "Share with someone stuck in their own way.",
        "Philosophy for real life. Not textbooks.",
    ]
    cta_q = random.choice(cta_questions)
    cta_s = random.choice(cta_statements)

    variant_a = (
        f"{hook_text}\n\n"
        f'"{quote}"\n'
        f"— {philosopher}\n\n"
        f"{cta_q}"
    )

    context_lines = [
        f"{philosopher} didn't write this. He said it.",
        f"Ancient philosophy. Modern problems. Same truth.",
        f"2,400 years old. Still hits different.",
    ]
    context = random.choice(context_lines)

    variant_b = (
        f'"{quote}"\n'
        f"— {philosopher}\n\n"
        f"{context}\n\n"
        f"{cta_s}"
    )

    return {"variant_a": variant_a, "variant_b": variant_b}


# ── Point 51: TikTok Cross-Post Format ───────────────────────────────────────


def export_for_tiktok(
    reel_path: Path | str,
    output_dir: Path | str,
    timestamp: str = "0",
    target_fps: int = 30,
) -> Path | None:
    """
    Point 51: Export reel for TikTok.
    TikTok spec: H.264, 9:16, ≤60fps, ≤4GB, ≤60s, stereo AAC 44.1kHz.
    Instagram Reels are already 9:16 at 1080×1920, so this is mostly
    a remux + audio normalisation pass.
    """
    reel_path = Path(reel_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"tiktok_{timestamp}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(reel_path),
        # Re-encode to ensure TikTok compatibility
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-r", str(target_fps),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        # Audio: stereo, 44.1kHz, 192kbps
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [tiktok] export failed: {result.stderr[-300:]}")
        return None
    print(f"  [tiktok] exported → {out_path.name}")
    return out_path


def get_tiktok_caption(
    quote: str,
    philosopher: str = "Socrates",
    hook_text: str = "",
) -> str:
    """
    Point 51: Generate TikTok-optimised caption.
    TikTok: front-load hashtags, emojis drive CTR, no external links.
    """
    tags = (
        "#philosophy #stoic #ancientphilosophy #quotes #mindset "
        "#lifecoach #motivation #wisdom #selfimprovement #fyp"
    )
    cap = hook_text or f'"{quote[:60]}"'
    return (
        f"{cap}\n\n"
        f"— {philosopher}\n\n"
        f"{tags}"
    )


# ── Point 52: YouTube Shorts Export ──────────────────────────────────────────


def export_for_youtube_shorts(
    reel_path: Path | str,
    output_dir: Path | str,
    timestamp: str = "0",
) -> Path | None:
    """
    Point 52: Export reel for YouTube Shorts.
    YT Shorts spec: 9:16, ≤60s, 1080×1920, H.264, AAC.
    Already 9:16 from Instagram — remux + minor re-encode.
    """
    reel_path = Path(reel_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"yt_short_{timestamp}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(reel_path),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-vf", "scale=1080:1920",
        "-c:a", "aac",
        "-b:a", "160k",
        "-ar", "48000",
        "-movflags", "+faststart",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  [yt-shorts] export failed: {result.stderr[-300:]}")
        return None
    print(f"  [yt-shorts] exported → {out_path.name}")
    return out_path


def get_youtube_shorts_metadata(
    quote: str,
    philosopher: str = "Socrates",
    hook_text: str = "",
) -> dict[str, str]:
    """
    Point 52: Generate YouTube Shorts title, description, and tags.
    YT Shorts: ≤100 char title, #Shorts in description triggers short player.
    """
    title = hook_text or f'"{quote[:70]}"'
    if len(title) > 95:
        title = title[:92] + "..."

    description = (
        f'"{quote}"\n'
        f"— {philosopher}\n\n"
        "#Shorts #Philosophy #Stoicism #AncientWisdom #Quotes #Mindset"
    )

    tags = "Philosophy,Stoicism,Socrates,Ancient Wisdom,Mindset,Quotes,Self Improvement"

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category": "22",   # YouTube category: People & Blogs
    }
