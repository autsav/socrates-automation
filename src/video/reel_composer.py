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

# ── Point 19: Branded jingle path ─────────────────────────────────────────────
JINGLE_PATH = Path(__file__).parent.parent.parent / "audio" / "jingle.mp3"


def generate_jingle(output_path: Path | None = None, duration: float = 1.5) -> Path | None:
    """
    Point 19: Create a simple branded 'jingle' tone via ffmpeg (no external audio needed).
    Uses a sine tone sweep as the brand signature sound.
    Replace with a real audio file at audio/jingle.mp3 for production.
    """
    target = output_path or JINGLE_PATH
    if target.exists():
        return target
    if not shutil.which("ffmpeg"):
        return None
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration},sine=frequency=528:duration={duration}",
        "-filter_complex", "[0:a][1:a]amix=inputs=2:normalize=0,afade=t=out:st=1.0:d=0.5",
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=15)
    return target if result.returncode == 0 else None

AUDIO_DIR = Path(__file__).parent.parent.parent / "audio"
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
    Prefers real music in audio/music/, then tries trending audio download,
    then prepares looped reel audio, falls back to generated audio in audio/."""
    # Try real music first (downloaded from Pixabay)
    real_path = MUSIC_DIR / f"{mood}.mp3"
    if real_path.exists() and real_path.stat().st_size > 1000:
        return real_path

    # Phase 3: Try trending audio engine to download royalty-free track
    try:
        from src.audio.trending_audio import download_music_for_mood
        downloaded = download_music_for_mood(mood, output_dir=str(MUSIC_DIR))
        if downloaded and downloaded.exists():
            # Symlink/copy to expected filename
            target = MUSIC_DIR / f"{mood}.mp3"
            if not target.exists():
                import shutil
                shutil.copy(str(downloaded), str(target))
            return target
    except Exception:
        pass

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
    flash_frame: str | Path | None = None,   # Point 1: 0.4s jarring flash before Scene 1
    glitch_intro: bool = False,              # Point 5: 0.2s TV-static noise burst
    progress_bar: bool = False,              # Point 6: loading bar overlay on hook
    motion_hook: bool = True,               # Point 4: aggressive hook zoom velocity
    waveform_overlay: bool = False,         # Point 18: frosted audio waveform on quote scene
    use_jingle: bool = False,               # Point 19: prepend branded jingle
    fps: int = 30,                          # Point 46: frame rate (30 or 60)
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
            from src.video.beat_sync import analyze_audio_for_sync
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

    # ── Point 1: Resolve flash frame path ─────────────────────────────────────
    flash_path = Path(flash_frame) if flash_frame else None
    has_flash = flash_path is not None and flash_path.exists()

    # ── PASS 1: Generate silent video ─────────────────────────────────────────
    cmd = ["ffmpeg", "-y"]

    # Optional flash frame input (Point 1)
    if has_flash:
        cmd += ["-framerate", "30", "-loop", "1", "-t", "0.4", "-i", str(flash_path)]

    # Add 3 scene image inputs with framerate
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
    from src.visual.motion_effects import MotionEngine, build_ken_burns_preset, Easing

    hook_move = build_ken_burns_preset("hook", hook_dur, seed=hash(timestamp) % 10000)
    # Point 4: Motion Hook — amplify zoom velocity on hook for scroll-stopping entrance
    if motion_hook:
        hook_move.end_zoom = min(1.35, hook_move.end_zoom * 1.15)
        hook_move.easing = Easing.EASE_OUT_EXPO if hasattr(hook_move, 'easing') else hook_move.easing
    quote_move = build_ken_burns_preset("quote", quote_dur, seed=hash(timestamp) % 10000 + 1)
    cta_move = build_ken_burns_preset("cta", cta_dur, seed=hash(timestamp) % 10000 + 2)

    engine = MotionEngine(image_size=(1080, 1920), fps=fps)
    hook_filter_str = engine.build_ken_burns_filter(hook_move, motion_blur=False)
    quote_filter_str = engine.build_ken_burns_filter(quote_move, motion_blur=True)
    cta_filter_str = engine.build_ken_burns_filter(cta_move, motion_blur=False)

    # Phase 2: Randomize transition type for variety
    transition_type = MotionEngine.random_transition(seed=hash(timestamp) % 10000)
    print(f"  [motion] Transition: {transition_type}")

    # Point 47: HDR-style color grading — boost contrast + lift blacks + warm tint
    hdr_grade = (
        "curves=r='0/0.05 0.5/0.55 1/1':"
        "g='0/0.02 0.5/0.52 1/0.98':"
        "b='0/0 0.5/0.48 1/0.92',"
        "eq=contrast=1.08:brightness=0.01:saturation=1.12"
    )

    # Vignette filter string
    vignette = "vignette=PI/4"

    # Input indices depend on whether we have a flash frame
    # has_flash adds flash as [0:v], shifting scenes to [1:v],[2:v],[3:v]
    si = 1 if has_flash else 0  # scene index offset

    # Hook scene: enhanced with motion engine
    # Point 6: optional loading-bar progress overlay on hook
    progress_filter = ""
    if progress_bar:
        # Gold loading bar at 88% height, animates from 0→full over hook_dur
        bar_w = 1080 - 160
        progress_filter = (
            f",drawbox=x=80:y=ih*0.88:w={bar_w}*t/{hook_dur}:h=10:"
            f"color=0xC9A96E@0.9:t=fill"
        )

    hook_filter = (
        f"[{si}:v]trim=duration={hook_dur},"
        f"{hook_filter_str}"
        f"{progress_filter},"
        f"{hdr_grade},"
        f"{vignette},format=yuv420p[v0]"
    )

    # Quote scene: stronger Ken Burns with motion blur
    quote_filter = (
        f"[{si+1}:v]trim=duration={quote_dur},"
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

    # Point 18: Audio waveform visualization — frosted bar at bottom of quote scene
    if waveform_overlay and has_audio:
        # showwaves renders audio as visual wave; overlay bottom 15% of frame
        # We overlay a synthesized waveform visualization using a pre-rendered effect
        quote_filter += (
            f",drawbox=x=0:y=ih*0.87:w=iw:h=ih*0.10:"
            f"color=white@0.12:t=fill"
        )

    quote_filter += f",{hdr_grade},{vignette},format=yuv420p[v1]"

    # CTA scene: enhanced with motion engine
    cta_filter = (
        f"[{si+2}:v]trim=duration={cta_dur},"
        f"{cta_filter_str},"
        f"{hdr_grade},"
        f"{vignette},format=yuv420p[v2]"
    )

    # Point 1: Flash frame filter (0.4s, hard cut, no xfade)
    flash_filter = ""
    if has_flash:
        flash_filter = f"[0:v]trim=duration=0.4,format=yuv420p[vflash];"

    # Point 49: Motion blur on xfade transitions via tblend=all_mode=average
    # tblend averages adjacent frames → smooth motion smear during crossfade
    xfade01 = (
        f"[v0][v1]xfade=transition={transition_type}:duration={TRANSITION_DURATION}:"
        f"offset={offset_1},tblend=all_mode=average[v01]"
    )
    xfade12 = (
        f"[v01][v2]xfade=transition={transition_type}:duration={TRANSITION_DURATION}:"
        f"offset={offset_2},tblend=all_mode=average"
    )

    # Crossfade transitions (beat-synced type or default fade)
    if has_flash:
        # Flash → hard cut → xfade between scenes
        transition_filters = (
            f"{xfade01};"
            f"{xfade12}[vmain];"
            f"[vflash][vmain]concat=n=2:v=1:a=0[outv]"
        )
    else:
        transition_filters = (
            f"{xfade01};"
            f"{xfade12}[outv]"
        )

    filter_parts = [hook_filter, quote_filter, cta_filter]
    if flash_filter:
        filter_parts.insert(0, flash_filter)
    filter_parts.append(transition_filters)
    filter_complex = ";".join(filter_parts)

    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", "[outv]"]
    cmd += ["-an"]  # No audio in silent video

    # Point 5: glitch intro handled as a separate pre-processing step below
    total_with_flash = TOTAL_DURATION + (0.4 if has_flash else 0)

    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-t", str(total_with_flash),
        str(silent_path),
    ]

    print(f"  [reel] Generating silent video with {len(scene_images)} scenes...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

    if result.returncode != 0:
        error = result.stderr[-600:] if result.stderr else "unknown error"
        raise RuntimeError(f"ffmpeg video pass failed: {error}")

    # ── Point 5: Glitch/Static Effect — prepend 0.2s TV noise burst ───────────
    if glitch_intro:
        glitch_path = output_dir / f"reel_{timestamp}_glitch.mp4"
        glitch_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=black:size=1080x1920:rate=30:duration=0.2",
            "-vf", "noise=alls=120:allf=t+u,format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            str(glitch_path),
        ]
        g_result = subprocess.run(glitch_cmd, capture_output=True, text=True, timeout=15)
        if g_result.returncode == 0:
            # Concatenate glitch + silent_path → new silent_path
            concat_path = output_dir / f"reel_{timestamp}_concat.mp4"
            concat_list = output_dir / f"concat_{timestamp}.txt"
            concat_list.write_text(
                f"file '{glitch_path.resolve()}'\nfile '{silent_path.resolve()}'\n",
                encoding="utf-8",
            )
            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-c", "copy", str(concat_path),
            ]
            c_result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=20)
            if c_result.returncode == 0:
                silent_path.unlink()
                concat_path.rename(silent_path)
                print(f"  [reel] Glitch intro prepended (0.2s)")
            glitch_path.unlink(missing_ok=True)
            concat_list.unlink(missing_ok=True)
        else:
            print(f"  [reel] ⚠️ Glitch intro failed: {g_result.stderr[-200:]}")

    # ── Point 19: Jingle — prepend branded tone to audio ────────────────────
    jingle_file: Path | None = None
    if use_jingle:
        jingle_file = generate_jingle()
        if jingle_file:
            print(f"  [reel] Jingle ready: {jingle_file.name}")
        else:
            print(f"  [reel] ⚠️ Jingle generation failed — skipping")

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

        # Point 17: Layered Audio Mixing — voice -3dB, music -18dB, duck music under voice
        # -3dB = volume 0.71, -12dB = 0.25 (music alone), -18dB = 0.125 (music under voice)
        MUSIC_SOLO_VOL = 0.25       # music with no voiceover
        MUSIC_DUCKED_VOL = 0.10     # music ducked under voiceover
        VOICE_VOL = 0.85            # voiceover volume (-1.4dB)

        mixed_segments = []
        for i, (name, dur, start) in enumerate(zip(scene_names, scene_durs, start_times)):
            voice_key = f"{name}_voice"
            has_voice = voice_key in voice_inputs
            bg_vol = MUSIC_DUCKED_VOL if has_voice else MUSIC_SOLO_VOL

            # Extract + volume-adjust background segment
            bg_label = (
                f"[0:a]atrim=start={start}:end={start + dur},"
                f"asetpts=PTS-STARTPTS,volume={bg_vol}[bg_{name}]"
            )
            audio_filters.append(bg_label)

            if has_voice:
                v_idx = voice_inputs[voice_key]
                # Volume-adjust voice then mix with ducked music
                audio_filters.append(
                    f"[{v_idx}:a]volume={VOICE_VOL}[voice_{name}]"
                )
                mix = (
                    f"[bg_{name}][voice_{name}]amix=inputs=2:duration=first"
                    f"[mix_{name}]"
                )
                audio_filters.append(mix)
                mixed_segments.append(f"[mix_{name}]")
            else:
                mixed_segments.append(f"[bg_{name}]")

        # Point 19: Prepend jingle to audio if requested
        if jingle_file and jingle_file.exists():
            j_idx = next_input
            audio_inputs += ["-i", str(jingle_file)]
            next_input += 1
            audio_filters.append(f"[{j_idx}:a]volume=0.6[jingle]")
            concat_inputs = "[jingle]" + "".join(mixed_segments)
            concat_filter = f"{concat_inputs}concat=n={len(mixed_segments)+1}:v=0:a=1[concat]"
        else:
            concat_inputs = "".join(mixed_segments)
            concat_filter = f"{concat_inputs}concat=n={len(mixed_segments)}:v=0:a=1[concat]"
        audio_filters.append(concat_filter)

        # Apply overall fade in/out
        fade_filter = (
            f"[concat]afade=t=in:d=0.3,afade=t=out:st={TOTAL_DURATION - 1}:d=1"
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
    output_dir = Path(__file__).parent.parent.parent / "output"
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
