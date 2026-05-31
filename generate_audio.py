"""Generate ambient audio tracks for each mood using ffmpeg built-in synthesis.
100% original generated audio — no downloads or licenses needed."""

import subprocess
import shutil
import sys
import os

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio")

MOODS = {
    "calm_stoic": (
        "Soft pink noise drone — calming, meditative",
        ["-f", "lavfi", "-i", "anoisesrc=d=10:c=pink:a=0.5",
         "-af", "lowpass=f=400,volume=0.25",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
    "cinematic_hopeful": (
        "Warm rising pad — hopeful, uplifting",
        ["-f", "lavfi", "-i", "aevalsrc=sin(220*t)*exp(-t/10):d=10",
         "-af", "volume=0.3",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
    "dark_philosophical": (
        "Deep brown noise with low rumble — contemplative, dark",
        ["-f", "lavfi", "-i", "anoisesrc=d=10:c=brown:a=0.7",
         "-af", "lowpass=f=200,volume=0.3",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
    "dramatic_ancient": (
        "Tense low-frequency pulse — dramatic, epic",
        ["-f", "lavfi", "-i", "aevalsrc=sin(110*t)*sin(2*t):d=10",
         "-af", "volume=0.3",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
    "epic_warrior": (
        "Low drum-like pulse — powerful, determined",
        ["-f", "lavfi", "-i", "aevalsrc=sin(55*t)*sin(3*t):d=10",
         "-af", "volume=0.3",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
    "mystical_greek": (
        "Ethereal modulated tone — mystical, otherworldly",
        ["-f", "lavfi", "-i", "aevalsrc=sin(440*t+sin(220*t)*0.5):d=10",
         "-af", "volume=0.25",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
    "stark_minimal": (
        "Single sparse tone — minimal, stark",
        ["-f", "lavfi", "-i", "aevalsrc=sin(440*t)*exp(-t/2):d=10",
         "-af", "volume=0.3",
         "-c:a", "libmp3lame", "-q:a", "2"]
    ),
}


def prepare_reel_audio(
    mood: str,
    target_duration: float = 20.0,
    output_dir: str = "",
) -> str | None:
    """
    Prepare a looped, volume-normalized audio track for a Reel.
    Loops the 10s generated audio to target_duration and applies loudnorm.
    Returns path to processed MP3, or None if source audio missing.
    """
    if not shutil.which("ffmpeg"):
        return None

    source = os.path.join(AUDIO_DIR, f"{mood}.mp3")
    if not os.path.exists(source):
        # Try fallback mood
        source = os.path.join(AUDIO_DIR, "calm_stoic.mp3")
        if not os.path.exists(source):
            return None

    out_dir = output_dir if output_dir else AUDIO_DIR
    os.makedirs(out_dir, exist_ok=True)
    output = os.path.join(out_dir, f"{mood}_reel.mp3")

    # Loop audio to target duration + crossfade loop + loudnorm
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", source,
        "-af", f"aloop=loop=-1:size=10s,afade=t=in:d=0.5,afade=t=out:st={target_duration-1}:d=1,loudnorm=I=-14:TP=-1.5",
        "-t", str(target_duration),
        "-c:a", "libmp3lame", "-q:a", "2",
        output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return output
    return None


def generate_audio():
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)

    os.makedirs(AUDIO_DIR, exist_ok=True)

    for mood, (desc, args) in MOODS.items():
        output = os.path.join(AUDIO_DIR, f"{mood}.mp3")
        cmd = ["ffmpeg", "-y"] + args + [output]
        print(f"  Generating {mood}.mp3... ", end="", flush=True)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            size = os.path.getsize(output)
            print(f"OK ({size/1024:.1f} KB) — {desc}")
        else:
            error = result.stderr[-200:] if result.stderr else "unknown error"
            print(f"FAILED: {error}")


if __name__ == "__main__":
    generate_audio()
