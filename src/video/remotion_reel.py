"""
Remotion Reel generator — the professional-animation video path.

Renders the Instagram POV Reel with a React/Remotion project (``remotion/`` at
the repo root) that produces broadcast-quality, physics-driven text animations:
word-by-word spring reveals, animated mood-colored gradient + particle fields,
breathing vignette, and pattern-interrupt flashes.

The ONLY communication between Python and Remotion is a JSON bridge file. Python
writes ``remotion/public/reel-data.json`` and invokes ``npx remotion render``.

This path degrades gracefully: if Node.js or the Remotion project isn't installed,
``generate_remotion_reel`` returns ``None`` so callers can fall back to the
ffmpeg-based POV generator (``src.video.pov_reel_generator``).

Usage:
    from src.video.remotion_reel import generate_remotion_reel

    path = generate_remotion_reel(
        hook="Purpose doesn't find you. You find it.",
        quote="The beginning of wisdom is the desire to learn.",
        attribution="— Socrates",
        cta="Save this. You'll need it again.",
        mood="dark_philosophical",
        output_path="output/reel.mp4",
    )
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from src.video import beat_sync

# Repo root: src/video/remotion_reel.py -> src -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTION_DIR = REPO_ROOT / "remotion"
BRIDGE_FILE = REMOTION_DIR / "public" / "reel-data.json"
COMPOSITION_ID = "PovReel"
ENTRY_POINT = "src/index.ts"

MIN_DURATION = 7.0
MAX_DURATION = 15.0

# The 7 moods the theme.ts palette supports. Anything else falls back to the
# first (dark_philosophical) inside Remotion, but we keep the list here so the
# Python side can validate/round-trip too.
SUPPORTED_MOODS = (
    "dark_philosophical",
    "dramatic_ancient",
    "cinematic_hopeful",
    "stark_minimal",
    "epic_warrior",
    "mystical_greek",
    "calm_stoic",
)


def node_available() -> bool:
    """True if a Node.js runtime is on PATH."""
    return shutil.which("node") is not None


def remotion_available() -> bool:
    """True if Node.js is installed AND the Remotion project's deps are present.

    We check for ``remotion/node_modules/remotion`` rather than shelling out, so
    the check is fast and side-effect free.
    """
    if not node_available():
        return False
    if not (REMOTION_DIR / "package.json").exists():
        return False
    if not (REMOTION_DIR / "node_modules" / "remotion").exists():
        return False
    return True


def _clamp_duration(quote: str, duration: float | None) -> float:
    """Pick a sensible reel duration, scaled with quote length when unset."""
    if duration is None:
        duration = min(MAX_DURATION, max(MIN_DURATION, 8.0 + len(quote) / 90))
    return max(MIN_DURATION, min(MAX_DURATION, float(duration)))


def _probe_duration(path: Path) -> float | None:
    """Best-effort media duration in seconds via ffprobe; None if unavailable."""
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        s = (r.stdout or "").strip()
        return round(float(s), 3) if r.returncode == 0 and s else None
    except Exception:  # pragma: no cover - defensive
        return None


def _loudnorm(path: Path, timeout: int = 120) -> None:
    """Best-effort EBU R128 loudness normalization to a social target.

    Replaces `path` in place with a normalized copy. Never raises; if ffmpeg is
    absent or fails, the original render is kept.
    """
    if not shutil.which("ffmpeg"):
        return
    tmp = path.with_suffix(".norm.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "copy", str(tmp),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(path)
        else:
            tmp.unlink(missing_ok=True)
    except Exception as e:  # pragma: no cover - defensive
        print(f"  [remotion] loudnorm skipped ({e})")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _synth_sfx(dest_dir: Path) -> dict | None:
    """Synthesize whoosh + impact SFX with ffmpeg into dest_dir. Best-effort;
    returns {'whoosh':name,'impact':name} for the ones produced, else None."""
    if not shutil.which("ffmpeg"):
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}
    whoosh = dest_dir / "sfx-whoosh.wav"
    impact = dest_dir / "sfx-impact.wav"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.4:c=pink:a=0.35",
             "-af", "bandpass=f=1400:width_type=h:w=1800,afade=t=in:d=0.06,afade=t=out:st=0.24:d=0.16",
             "-ac", "1", str(whoosh)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and whoosh.exists():
            result["whoosh"] = whoosh.name
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=85:duration=0.22",
             "-af", "afade=t=out:st=0.03:d=0.19", "-ac", "1", str(impact)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and impact.exists():
            result["impact"] = impact.name
    except Exception:  # pragma: no cover - defensive
        pass
    return result or None


def write_bridge_file(
    hook: str,
    quote: str,
    attribution: str,
    cta: str,
    mood: str,
    duration: float,
    fps: int,
    bridge_path: Path = BRIDGE_FILE,
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    music_path: Path | None = None,
    hook_words: list | None = None,
    quote_words: list | None = None,
    cta_words: list | None = None,
) -> Path:
    """Write the reel-data.json bridge file the Remotion composition reads.

    Up to three voiceover tracks (``hook_voice``/``quote_voice``/``cta_voice``)
    and one music track (``music_path``) are copied next to the bridge as
    ``vo-hook<ext>``/``vo-quote<ext>``/``vo-cta<ext>``/``music<ext>`` and
    referenced via the ``voices``/``music`` keys so Remotion's ``<Audio>``
    (via ``staticFile``) can play — and bake — them into the render. Per-voice
    durations (best-effort, via ffprobe) are written as ``voiceDurations``.
    Beats are detected from ``quote_voice`` (absolute seconds) and written as
    ``beats``. With no audio, ``voices``/``voiceDurations`` are all-``None``,
    ``beats`` is ``[]``, and ``music`` is omitted, giving the original
    silent-reel behavior.

    Returns the path written. Exposed separately so tests can exercise it
    without invoking Node.
    """
    if mood not in SUPPORTED_MOODS:
        mood = SUPPORTED_MOODS[0]

    def _copy_audio(src: Path, name: str) -> str | None:
        try:
            bridge_path.parent.mkdir(parents=True, exist_ok=True)
            dst = bridge_path.parent / name
            # Source may already sit at the destination path (e.g. tests that
            # stage fixtures directly next to the bridge) — shutil.copy raises
            # SameFileError in that case even though nothing needs to happen.
            if src.resolve() != dst.resolve():
                shutil.copy(src, dst)
            return name
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] audio copy failed ({e})")
            return None

    voices: dict[str, str | None] = {"hook": None, "quote": None, "cta": None}
    voice_durations: dict[str, float | None] = {"hook": None, "quote": None, "cta": None}
    for key, p in (("hook", hook_voice), ("quote", quote_voice), ("cta", cta_voice)):
        if p and Path(p).exists():
            p = Path(p)
            nm = _copy_audio(p, f"vo-{key}{p.suffix}")
            if nm:
                voices[key] = nm
                voice_durations[key] = _probe_duration(p)

    music_name: str | None = None
    if music_path and Path(music_path).exists():
        mp = Path(music_path)
        music_name = _copy_audio(mp, f"music{mp.suffix}")

    beats: list[float] = []
    if quote_voice and Path(quote_voice).exists():
        try:
            beats = beat_sync.detect_beats(Path(quote_voice))
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] beat detection failed ({e}) — reel plays un-synced")
            beats = []

    sfx = _synth_sfx(bridge_path.parent)

    payload = {
        "hook": hook or "",
        "quote": quote or "",
        "attribution": attribution or "",
        "cta": cta or "",
        "mood": mood,
        "duration": round(float(duration), 3),
        "fps": int(fps),
        "beats": beats,
        "voices": voices,
        "voiceDurations": voice_durations,
        "wordTimes": {
            "hook": hook_words or [],
            "quote": quote_words or [],
            "cta": cta_words or [],
        },
    }
    if music_name:
        payload["music"] = music_name
    if sfx:
        payload["sfx"] = sfx

    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return bridge_path


def generate_remotion_reel(
    hook: str,
    quote: str,
    attribution: str = "— Socrates",
    cta: str = "",
    mood: str = "dark_philosophical",
    output_path: str | Path | None = None,
    duration: float | None = None,
    fps: int = 30,
    timeout: int = 600,
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    music_path: Path | None = None,
    hook_words: list | None = None,
    quote_words: list | None = None,
    cta_words: list | None = None,
) -> Path | None:
    """
    Render a POV Reel via Remotion (React-based, headless-browser rendering).

    Steps:
      1. Write the reel data to ``remotion/public/reel-data.json``.
      2. Run ``npx remotion render <entry> PovReel <output> --props=<bridge>``.
      3. Return the output MP4 path.

    Returns ``None`` (never raises) if Node/Remotion is unavailable or the render
    fails, so callers can fall back to the ffmpeg POV generator.
    """
    if output_path is None:
        output_path = REPO_ROOT / "output" / "remotion_reel.mp4"
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not remotion_available():
        print("  [remotion] Node/Remotion not installed — skipping (use POV fallback)")
        return None

    duration = _clamp_duration(quote, duration)

    # 1. Write the JSON bridge — the ONLY channel between Python and Remotion.
    bridge = write_bridge_file(
        hook=hook,
        quote=quote,
        attribution=attribution,
        cta=cta,
        mood=mood,
        duration=duration,
        fps=fps,
        hook_voice=hook_voice,
        quote_voice=quote_voice,
        cta_voice=cta_voice,
        music_path=music_path,
        hook_words=hook_words,
        quote_words=quote_words,
        cta_words=cta_words,
    )

    # 2. Invoke the Remotion CLI. --props takes a path to the JSON bridge file.
    cmd = [
        "npx",
        "remotion",
        "render",
        ENTRY_POINT,
        COMPOSITION_ID,
        str(output_path),
        f"--props={bridge}",
        "--log=error",
    ]

    print(f"  [remotion] Rendering Reel ({duration:.1f}s, mood={mood})...")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"  [remotion] ⚠️ Render timed out after {timeout}s — falling back")
        return None
    except Exception as e:  # pragma: no cover - defensive
        print(f"  [remotion] ⚠️ Render invocation failed: {e} — falling back")
        return None

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "unknown error")[-800:]
        print(f"  [remotion] ⚠️ Render failed — falling back to POV generator:\n{err}")
        return None

    if not output_path.exists():
        print("  [remotion] ⚠️ Render reported success but output missing — falling back")
        return None

    size = output_path.stat().st_size
    print(f"  [remotion] Saved: {output_path} ({size / 1024:.0f} KB)")
    _loudnorm(output_path)
    return output_path


if __name__ == "__main__":
    out = generate_remotion_reel(
        hook="Purpose doesn't find you. You find it.",
        quote="The unexamined life is not worth living.",
        attribution="— Socrates",
        cta="Save this before you forget it.",
        mood="dark_philosophical",
        output_path=REPO_ROOT / "output" / "remotion_demo.mp4",
    )
    print(out)
