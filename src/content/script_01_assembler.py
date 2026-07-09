"""
Script 01 Reel Assembler
Assembles the "Motivation Is a Myth" Reel from generated FLUX frames.
Uses ffmpeg for video composition with Ken Burns motion and text overlays.
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os

# ── Configuration ──────────────────────────────────────────────────────────────
FRAMES_DIR = Path("~/viral-lab/output/script_01_frames").expanduser()
OUTPUT_DIR = Path("~/viral-lab/output").expanduser()
OUTPUT_REEL = OUTPUT_DIR / "script_01_reel.mp4"

# Font setup
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
FONT_PATH = next((p for p in FONT_PATHS if Path(p).exists()), None)

# Reel specs
WIDTH, HEIGHT = 1080, 1920
FPS = 30

# Scene definitions: (image_name, duration, text_lines, text_position)
SCENES = [
    # HOOK: "You've been lied to." — Text on dark background
    (None, 3.0, ["You've been lied to."], "center"),
    # SETUP: Philosopher in study
    ("hook_study.jpg", 5.0, ["The Stoics called it", "something else entirely."], "lower"),
    # ESCALATION 1: Fire (Motivation is a feeling)
    ("fire.jpg", 3.0, ["Motivation is a feeling."], "center"),
    # ESCALATION 1: Stone (Discipline is a choice)
    ("stone.jpg", 3.0, ["Discipline is a choice."], "center"),
    # ESCALATION 2: Philosopher close-up
    ("philosopher_close.jpg", 3.0, ["And only one of them", "shows up when you need it."], "upper"),
    # PAYOFF: Quote on dark
    (None, 2.5, ["Motivation gets you started.", "Discipline makes you unstoppable."], "center"),
    # LOOP/CTA
    (None, 2.0, ["Follow for more", "uncomfortable truths."], "center"),
]

# Colors
BG_DARK = "#1a1a2e"
TEXT_COLOR = "#f5f0e6"
GOLD = "#c9a227"


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Load font or fallback."""
    if FONT_PATH and Path(FONT_PATH).exists():
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


def _draw_text_on_image(img: Image.Image, lines: list[str], position: str) -> Image.Image:
    """Draw text on image with proper styling."""
    draw = ImageDraw.Draw(img)
    
    # Font sizes
    if len(lines) == 1 and len(lines[0]) < 40:
        font_size = 72
    elif len(lines) == 1:
        font_size = 56
    else:
        font_size = 52
    
    font = _get_font(font_size)
    
    # Calculate text block size
    line_heights = []
    max_width = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_heights.append(h)
        max_width = max(max_width, w)
    
    total_height = sum(line_heights) + (len(lines) - 1) * 20
    
    # Position
    if position == "center":
        x = (WIDTH - max_width) // 2
        y = (HEIGHT - total_height) // 2
    elif position == "lower":
        x = (WIDTH - max_width) // 2
        y = HEIGHT * 3 // 4 - total_height // 2
    elif position == "upper":
        x = (WIDTH - max_width) // 2
        y = HEIGHT // 4 - total_height // 2
    else:
        x = (WIDTH - max_width) // 2
        y = (HEIGHT - total_height) // 2
    
    # Draw semi-transparent background panel
    padding = 40
    panel_x = x - padding
    panel_y = y - padding
    panel_w = max_width + padding * 2
    panel_h = total_height + padding * 2
    
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        fill=(26, 26, 46, 180),  # Dark indigo with transparency
        outline=None,
    )
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    
    # Draw text with shadow
    current_y = y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_x = (WIDTH - line_w) // 2
        
        # Shadow
        draw.text((line_x + 3, current_y + 3), line, font=font, fill=(0, 0, 0))
        # Main text
        draw.text((line_x, current_y), line, font=font, fill=TEXT_COLOR)
        
        current_y += line_heights[lines.index(line)] + 20
    
    return img


def _create_scene_frame(image_path: Path | None, lines: list[str], position: str) -> Image.Image:
    """Create a single scene frame."""
    if image_path and image_path.exists():
        img = Image.open(image_path).convert('RGB')
        # Resize to 1080x1920 maintaining aspect ratio
        img.thumbnail((WIDTH, HEIGHT), Image.LANCZOS)
        # Create canvas and center
        canvas = Image.new('RGB', (WIDTH, HEIGHT), BG_DARK)
        x = (WIDTH - img.width) // 2
        y = (HEIGHT - img.height) // 2
        canvas.paste(img, (x, y))
        img = canvas
    else:
        # Solid dark background
        img = Image.new('RGB', (WIDTH, HEIGHT), BG_DARK)
    
    return _draw_text_on_image(img, lines, position)


def assemble_reel():
    """Assemble the full Reel video."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("❌ ffmpeg not found")
        return False
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate individual scene images
    scene_images = []
    for i, (img_name, duration, lines, position) in enumerate(SCENES):
        img_path = FRAMES_DIR / img_name if img_name else None
        frame = _create_scene_frame(img_path, lines, position)
        frame_path = OUTPUT_DIR / f"script_01_scene_{i:02d}.jpg"
        frame.save(frame_path, quality=95)
        scene_images.append((frame_path, duration))
        print(f"  Scene {i}: {img_name or 'dark bg'} — {duration}s")
    
    # Build ffmpeg concat file
    concat_file = OUTPUT_DIR / "script_01_concat.txt"
    with open(concat_file, "w") as f:
        for img_path, duration in scene_images:
            f.write(f"file '{img_path}'\n")
            f.write(f"duration {duration}\n")
        # Repeat last frame
        f.write(f"file '{scene_images[-1][0]}'\n")
    
    # Get voiceover
    voiceover_path = FRAMES_DIR / "src.audio.voiceover.mp3"
    has_voiceover = voiceover_path.exists()
    
    # Build ffmpeg command
    # Correct ordering: input options → -i → input options → -i → output options → output
    cmd = [
        ffmpeg, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
    ]
    
    if has_voiceover:
        cmd.extend(["-i", str(voiceover_path)])
    
    # Output options
    cmd.extend([
        "-vf", f"fps={FPS},format=yuv420p",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
    ])
    
    if has_voiceover:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
        ])
    else:
        cmd.append("-an")
    
    cmd.append(str(OUTPUT_REEL))
    
    print(f"\n🎬 Assembling Reel...")
    print(f"   Command: {' '.join(cmd[:10])} ...")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        size_mb = OUTPUT_REEL.stat().st_size / (1024 * 1024)
        print(f"✅ Reel assembled: {OUTPUT_REEL}")
        print(f"   Size: {size_mb:.1f} MB")
        print(f"   Duration: {sum(d for _, d in scene_images):.1f}s")
        return True
    else:
        print(f"❌ ffmpeg failed:\n{result.stderr}")
        return False


if __name__ == "__main__":
    success = assemble_reel()
    exit(0 if success else 1)
