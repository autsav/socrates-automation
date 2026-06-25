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
    voiceover: dict | None = None,
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
    silent_path = output_dir / f"reel_{timestamp}_silent.mp4"

    audio = _audio_path(mood)
    has_audio = audio is not None
    has_voiceover = voiceover is not None and any(
        voiceover.get(k) for k in ("hook_voice", "quote_voice", "cta_voice")
    )

    # ── Beat Sync: detect energy peaks and align transitions ─────────────────
    beat_sync_info = None
    if has_audio:
        try:
            from beat_sync import analyze_audio_for_sync
            beat_sync_info = analyze_audio_for_sync(audio, mood=mood, target_total=TOTAL_DURATION)
            print(f"  [beat-sync] Peaks: {beat_sync_info['peaks'][:3]}")
            print(f"  [beat-sync] Scenes: {beat_sync_info['scene_durations']}, transition: {beat_sync_info['transition_type']}")
        except Exception as e:
            print(f"  [beat-sync] Analysis failed ({e}) — using default timing")

    if beat_sync_info and beat_sync_info["used_beats"]:
        hook_dur, quote_dur, cta_dur = beat_sync_info["scene_durations"]
        offset_1, offset_2 = beat_sync_info["transition_offsets"]
        transition_type = beat_sync_info["transition_type"]
    else:
        # Fallback to fixed psychology-optimised timing
        hook_dur, quote_dur, cta_dur = SCENE_DURATIONS
        offset_1 = hook_dur - TRANSITION_DURATION          # 2.5
        v01_dur = hook_dur + quote_dur - TRANSITION_DURATION  # 17.5
        offset_2 = v01_dur - TRANSITION_DURATION           # 17.0
        transition_type = "fade"

    zoom_frames = int(quote_dur * 30)  # frames for quote scene @ 30fps

    # ── PASS 1: Generate silent video ─────────────────────────────────────────
    cmd = ["ffmpeg", "-y"]

    # Add 3 image inputs with framerate
    for img_path in scene_paths:
        cmd += ["-framerate", "30", "-loop", "1", "-i", str(img_path)]

    # ── Build video filter_complex ──────────────────────────────────────────
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

    # ── Phase 2: Motion Effects — enhanced camera movement ────────────────────
    from motion_effects import MotionEngine, build_ken_burns_preset

    hook_move = build_ken_burns_preset("hook", hook_dur, seed=hash(timestamp) % 10000)
    quote_move = build_ken_burns_preset("quote", quote_dur, seed=hash(timestamp) % 10000 + 1)
    cta_move = build_ken_burns_preset("cta", cta_dur, seed=hash(timestamp) % 10000 + 2)

    engine = MotionEngine(image_size=(1080, 1920), fps=30)
    hook_filter_str = engine.build_ken_burns_filter(hook_move, motion_blur=False)
    quote_filter_str = engine.build_ken_burns_filter(quote_move, motion_blur=True)
    cta_filter_str = engine.build_ken_burns_filter(cta_move, motion_blur=False)

    # Phase 2: Randomize transition type for variety
    transition_type = MotionEngine.random_transition(seed=hash(timestamp) % 10000)
    print(f"  [motion] Transition: {transition_type}")

    # Vignette filter string
    vignette = "vignette=PI/4"

    # Hook scene: enhanced with motion engine
    hook_filter = (
        f"[0:v]trim=duration={hook_dur},"
        f"{hook_filter_str},"
        f"{vignette},format=yuv420p[v0]"
    )

    # Quote scene: stronger Ken Burns with motion blur
    quote_filter = (
        f"[1:v]trim=duration={quote_dur},"
        f"{quote_filter_str}"
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

    quote_filter += f",{vignette},format=yuv420p[v1]"

    # CTA scene: enhanced with motion engine
    cta_filter = (
        f"[2:v]trim=duration={cta_dur},"
        f"{cta_filter_str},"
        f"{vignette},format=yuv420p[v2]"
    )

    # Crossfade transitions (beat-synced type or default fade)
    transition_filters = (
        f"[v0][v1]xfade=transition={transition_type}:duration={TRANSITION_DURATION}:offset={offset_1}[v01];"
        f"[v01][v2]xfade=transition={transition_type}:duration={TRANSITION_DURATION}:offset={offset_2}[outv]"
    )

    filter_complex = ";".join([hook_filter, quote_filter, cta_filter, transition_filters])

    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", "[outv]"]
    cmd += ["-an"]  # No audio in silent video
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-t", str(TOTAL_DURATION),
        str(silent_path),
    ]

    print(f"  [reel] Generating silent video with {len(scene_images)} scenes...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

    if result.returncode != 0:
        error = result.stderr[-600:] if result.stderr else "unknown error"
        raise RuntimeError(f"ffmpeg video pass failed: {error}")

    # ── PASS 2: Mix audio (background music + voiceover) ────────────────────
    if has_audio or has_voiceover:
        # Build mixed audio track
        mixed_audio_path = output_dir / f"audio_{timestamp}.m4a"

        # Strategy:
        # 1. Extract background music segments for each scene
        # 2. Mix each segment with corresponding voiceover
        # 3. Concatenate all mixed segments
        # 4. Apply overall fade in/out

        audio_inputs = []
        audio_filters = []

        # Background music is input 0
        if has_audio:
            audio_inputs += ["-i", str(audio)]
            bg_idx = 0
        else:
            # Create silent audio track if no background music
            audio_inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
            bg_idx = 0

        # Voiceover inputs
        voice_inputs = {}
        next_input = 1
        for key in ("hook_voice", "quote_voice", "cta_voice"):
            path = voiceover.get(key) if voiceover else None
            if path and Path(path).exists():
                audio_inputs += ["-i", str(path)]
                voice_inputs[key] = next_input
                next_input += 1

        # Scene durations
        scene_durs = [hook_dur, quote_dur, cta_dur]
        scene_names = ["hook", "quote", "cta"]
        start_times = [0, hook_dur, hook_dur + quote_dur]

        mixed_segments = []
        for i, (name, dur, start) in enumerate(zip(scene_names, scene_durs, start_times)):
            # Extract background segment
            bg_label = f"[0:a]atrim=start={start}:end={start + dur},volume=0.20[bg_{name}]"
            audio_filters.append(bg_label)

            # Check if voiceover exists for this scene
            voice_key = f"{name}_voice"
            if voice_key in voice_inputs:
                v_idx = voice_inputs[voice_key]
                # Mix voiceover with background
                mix = (
                    f"[bg_{name}][{v_idx}:a]amix=inputs=2:duration=shortest:weights='0.3 1.0'"
                    f"[mix_{name}]"
                )
                audio_filters.append(mix)
                mixed_segments.append(f"[mix_{name}]")
            else:
                mixed_segments.append(f"[bg_{name}]")

        # Concatenate all mixed segments
        concat_inputs = "".join(mixed_segments)
        concat_filter = f"{concat_inputs}concat=n={len(mixed_segments)}:v=0:a=1[concat]"
        audio_filters.append(concat_filter)

        # Apply overall fade in/out
        fade_filter = (
            f"[concat]afade=t=in:d=0.5,afade=t=out:st={TOTAL_DURATION - 1}:d=1"
            f"[outa]"
        )
        audio_filters.append(fade_filter)

        audio_cmd = ["ffmpeg", "-y"] + audio_inputs
        audio_cmd += ["-filter_complex", ";".join(audio_filters)]
        audio_cmd += ["-map", "[outa]"]
        audio_cmd += [
            "-c:a", "aac",
            "-b:a", "160k",
            "-t", str(TOTAL_DURATION),
            str(mixed_audio_path),
        ]

        print(f"  [reel] Mixing audio ({'voiceover + ' if has_voiceover else ''}background music)...")
        audio_result = subprocess.run(audio_cmd, capture_output=True, text=True, timeout=60)

        if audio_result.returncode != 0:
            error = audio_result.stderr[-400:] if audio_result.stderr else "unknown error"
            print(f"  [reel] ⚠️ Audio mixing failed: {error}")
            print(f"  [reel] Using silent video without audio")
            mixed_audio_path = None
    else:
        mixed_audio_path = None

    # ── PASS 3: Combine silent video + mixed audio ─────────────────────────
    final_cmd = ["ffmpeg", "-y", "-i", str(silent_path)]
    if mixed_audio_path and mixed_audio_path.exists():
        final_cmd += ["-i", str(mixed_audio_path)]
        final_cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest"]
    else:
        final_cmd += ["-c:v", "copy", "-an"]

    final_cmd += [str(output_path)]

    print(f"  [reel] Combining video + audio...")
    final_result = subprocess.run(final_cmd, capture_output=True, text=True, timeout=30)

    if final_result.returncode != 0:
        error = final_result.stderr[-400:] if final_result.stderr else "unknown error"
        raise RuntimeError(f"ffmpeg final combine failed: {error}")

    # Clean up temp files
    if silent_path.exists():
        silent_path.unlink()
    if mixed_audio_path and mixed_audio_path.exists():
        mixed_audio_path.unlink()

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
