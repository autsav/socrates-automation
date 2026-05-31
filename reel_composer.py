"""
Reel Composer — assembles 3 scene images into a 15-second Reel video
with crossfade transitions, Ken Burns zoom, and ambient background audio.

Flow: 3 × 1080x1920 vertical JPEGs + mood-based audio → 15s MP4 video
Requires: ffmpeg 4.4+ with xfade filter support

Psychology-optimised timing (research: 7-15s = peak completion rate):
  Scene 1 (Hook):  4s  — pattern interrupt, must land the curiosity gap
  Scene 2 (Quote): 8s  — enough to read + feel the quote
  Scene 3 (CTA):   3s  — share trigger, no fluff
Total: 15s (was 21s — shorter = higher completion = more algorithmic push)
"""

import subprocess
import shutil
import time
from pathlib import Path

AUDIO_DIR = Path(__file__).parent / "audio"
MUSIC_DIR = AUDIO_DIR / "music"
FALLBACK_MOOD = "calm_stoic"

# Mood → audio file mapping (fallback generated audio)
MOOD_AUDIO = {
    "calm_stoic": "calm_stoic.mp3",
    "cinematic_hopeful": "cinematic_hopeful.mp3",
    "dark_philosophical": "dark_philosophical.mp3",
    "dramatic_ancient": "dramatic_ancient.mp3",
    "epic_warrior": "epic_warrior.mp3",
    "mystical_greek": "mystical_greek.mp3",
    "stark_minimal": "stark_minimal.mp3",
}

# Scene durations (seconds) — psychology-optimised for completion rate
# Research: 7-15s Reels have 5-10x more reach than longer ones.
# Hook 4s: enough for pattern interrupt. Quote 8s: readable + felt. CTA 3s: sharp exit.
SCENE_DURATIONS = [4, 8, 3]   # Hook, Quote, CTA  (was [3, 15, 3] = 21s)
TRANSITION_DURATION = 0.5      # Crossfade length
TOTAL_DURATION = sum(SCENE_DURATIONS) - 2 * TRANSITION_DURATION  # 14s


def ffmpeg_available() -> bool:
    """Check if ffmpeg is installed and usable."""
    return shutil.which("ffmpeg") is not None


def _xfade_available() -> bool:
    """Check if ffmpeg supports the xfade filter (requires 4.4+)."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=10
        )
        return "xfade" in result.stdout
    except Exception:
        return False


def _audio_path(mood: str, output_dir: str = "output") -> Path | None:
    """Get path to audio file for the given mood.
    Prefers real music in audio/music/, then prepares looped reel audio,
    falls back to generated audio in audio/."""
    # Try real music first (downloaded from Pixabay)
    real_path = MUSIC_DIR / f"{mood}.mp3"
    if real_path.exists() and real_path.stat().st_size > 1000:
        return real_path

    # Prepare looped, normalized reel audio from generated tracks
    try:
        from generate_audio import prepare_reel_audio
        reel_audio = prepare_reel_audio(mood, target_duration=TOTAL_DURATION, output_dir=output_dir)
        if reel_audio:
            return Path(reel_audio)
    except Exception:
        pass

    # Ultimate fallback: raw generated audio
    filename = MOOD_AUDIO.get(mood)
    if not filename:
        filename = MOOD_AUDIO.get(FALLBACK_MOOD)
    path = AUDIO_DIR / filename
    return path if path.exists() else None


# Font paths for burned-in subtitles (Ubuntu runner fonts)
_SUBTITLE_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def _subtitle_font_path() -> str:
    """Return first available system font for ffmpeg drawtext."""
    for path in _SUBTITLE_FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return ""


def generate_reel(
    scene_images: list[str | Path],
    mood: str,
    output_dir: str = "output",
    timestamp: str | None = None,
    quote_text: str = "",
) -> Path | None:
    """
    Generate a 20-second Reel video from 3 scene images with crossfade
    transitions, Ken Burns zoom/pan on the quote scene, burned-in subtitles,
    vignette effect, and improved encoding quality.

    Args:
        scene_images: List of 3 paths to 1080x1920 JPEGs
                      [hook_scene, quote_scene, cta_scene]
        mood: Image mood string (calm_stoic, cinematic_hopeful, etc.)
        output_dir: Directory to save the MP4
        timestamp: String for filename. Auto-generated if None.
        quote_text: Quote text for burned-in subtitles on Scene 2.

    Returns:
        Path to the generated MP4, or None if ffmpeg is not available.
    """
    if not ffmpeg_available():
        print("  [reel] ffmpeg not found — skipping reel generation")
        return None

    if len(scene_images) != 3:
        raise ValueError(f"Expected 3 scene images, got {len(scene_images)}")

    scene_paths = [Path(p) for p in scene_images]
    for p in scene_paths:
        if not p.exists():
            raise FileNotFoundError(f"Scene image not found: {p}")

    if timestamp is None:
        timestamp = str(int(time.time()))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"reel_{timestamp}.mp4"

    audio = _audio_path(mood)
    has_audio = audio is not None

    # Scene durations (seconds)
    hook_dur, quote_dur, cta_dur = SCENE_DURATIONS
    offset_1 = hook_dur - TRANSITION_DURATION          # 2.5
    v01_dur = hook_dur + quote_dur - TRANSITION_DURATION  # 17.5
    offset_2 = v01_dur - TRANSITION_DURATION           # 17.0

    zoom_frames = quote_dur * 30  # 450 frames for 15s @ 30fps

    cmd = ["ffmpeg", "-y"]

    # Add 3 image inputs with framerate
    for img_path in scene_paths:
        cmd += ["-framerate", "30", "-loop", "1", "-i", str(img_path)]

    # Add audio input if available
    audio_input_idx = 3
    if has_audio:
        cmd += ["-i", str(audio)]

    # ── Build filter_complex ────────────────────────────────────────────────
    # Scene 1 (hook): subtle zoom-in for energy
    # Scene 2 (quote): Ken Burns zoom + pan + subtitles + vignette
    # Scene 3 (cta): static + vignette

    font_path = _subtitle_font_path()
    has_font = bool(font_path)

    # Subtitle text: wrap to ~30 chars per line for readability
    sub_lines = []
    if quote_text:
        words = quote_text.split()
        line = []
        for w in words:
            if sum(len(x) for x in line) + len(w) + len(line) > 30 and line:
                sub_lines.append(" ".join(line))
                line = [w]
            else:
                line.append(w)
        if line:
            sub_lines.append(" ".join(line))
    sub_text = "\\n".join(sub_lines) if sub_lines else ""

    # Vignette filter string
    vignette = "vignette=PI/4"

    # Hook scene: subtle zoom-in from 1.0 to 1.03
    hook_filter = (
        f"[0:v]trim=duration={hook_dur},"
        f"zoompan=z='min(zoom+0.0010,1.03)':d={hook_dur*30}:s=1080x1920:fps=30,"
        f"{vignette},format=yuv420p[v0]"
    )

    # Quote scene: stronger Ken Burns zoom 1.0→1.12 with horizontal pan
    quote_filter = (
        f"[1:v]trim=duration={quote_dur},"
        f"zoompan=z='min(zoom+0.0015,1.12)':d={zoom_frames}:s=1080x1920:fps=30"
        f":x='(iw-iw/zoom)/2+sin(t/15*PI)*40',"
        f"{vignette}"
    )

    # Add burned-in subtitles if font available and text present
    if has_font and sub_text:
        # Write text to temp file to avoid shell escaping hell
        sub_file = output_dir / f"sub_{timestamp}.txt"
        sub_file.write_text(sub_text, encoding="utf-8")
        quote_filter += (
            f",drawtext=fontfile={font_path}:textfile={str(sub_file)}:"
            f"fontsize=44:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h*0.72):"
            f"box=1:boxcolor=black@0.4:boxborderw=12:"
            f"line_spacing=8:shadowx=2:shadowy=2:shadowcolor=black@0.6"
        )

    quote_filter += ",format=yuv420p[v1]"

    # CTA scene: static with vignette
    cta_filter = (
        f"[2:v]trim=duration={cta_dur},"
        f"{vignette},format=yuv420p[v2]"
    )

    # Crossfade transitions
    transition_filters = (
        f"[v0][v1]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={offset_1}[v01];"
        f"[v01][v2]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={offset_2}[outv]"
    )

    filter_complex = ";".join([hook_filter, quote_filter, cta_filter, transition_filters])

    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", "[outv]"]

    if has_audio:
        cmd += ["-map", f"{audio_input_idx}:a:0"]
        cmd += [
            "-c:a", "aac",
            "-b:a", "160k",
            "-af", f"afade=t=in:d=0.5,afade=t=out:st={TOTAL_DURATION - 1}:d=1,volume=0.35,loudnorm",
        ]
    else:
        cmd += ["-an"]

    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-t", str(TOTAL_DURATION),
        str(output_path),
    ]

    print(f"  [reel] Generating 20s multi-scene reel{' with audio + subtitles' if has_audio and has_font else ' with audio' if has_audio else ' (silent)'}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

    if result.returncode != 0:
        error = result.stderr[-600:] if result.stderr else "unknown error"
        raise RuntimeError(f"ffmpeg failed: {error}")

    size = output_path.stat().st_size
    print(f"  [reel] Saved: {output_path} ({size / 1024:.0f} KB)")
    return output_path


if __name__ == "__main__":
    # Test with placeholder scene images
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create 3 test scene images
    from PIL import Image
    test_scenes = []
    for name in ["hook", "quote", "cta"]:
        img = Image.new("RGB", (1080, 1920), color=(30 + hash(name) % 50, 20, 10))
        path = output_dir / f"test_scene_{name}.jpg"
        img.save(path)
        test_scenes.append(path)

    result = generate_reel(test_scenes, mood="cinematic_hopeful")
    if result:
        print(f"Reel generated: {result}")
        subprocess.run([
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(result)
        ])
