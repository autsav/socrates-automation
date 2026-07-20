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
from src.video.word_classes import classify_words

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
        "-ar", "48000",            # Meta caps Reels audio at 48kHz; loudnorm upsamples to 96kHz (error 2207085)
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


def _emphasis_beats(words: list | None, max_beats: int = 2, min_gap: float = 1.2) -> list[float]:
    """Derive impact-SFX beat times (seconds, relative to the quote scene) from
    per-word timings.

    Acoustic beat detection (``beat_sync.detect_beats``) finds nothing on a short
    spoken-word clip via the ebur128 fallback, which left ``beats`` empty and the
    impact SFX (and camera punches) never fired. When that happens we place the
    impacts on the most *emphasized* words — the longest-spoken ones, which read
    as stresses — enforcing a minimum gap so two impacts never stack. Word times
    and beats share the same coordinate space (seconds from the quote scene
    start), so these align exactly with the narration.

    Returns up to ``max_beats`` timestamps, time-sorted. Empty if no usable words.
    """
    candidates: list[tuple[float, float]] = []
    for w in words or []:
        try:
            start = float(w["start"])
            dur = float(w["end"]) - start
        except (KeyError, TypeError, ValueError):
            continue
        if dur <= 0:
            continue
        candidates.append((dur, round(start, 3)))

    # Longest (most emphasized) first, then greedily keep beats that respect the gap.
    candidates.sort(reverse=True)
    picked: list[float] = []
    for _dur, t in candidates:
        if all(abs(t - p) >= min_gap for p in picked):
            picked.append(t)
        if len(picked) >= max_beats:
            break
    return sorted(picked)


def _synth_sfx(dest_dir: Path) -> dict | None:
    """Synthesize whoosh + impact + riser + sub_impact SFX with ffmpeg into
    dest_dir. Best-effort; returns the entries produced (a subset of
    {'whoosh','impact','riser','sub_impact'}), else None."""
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
    riser = dest_dir / "sfx-riser.wav"
    sub = dest_dir / "sfx-sub.wav"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=1.2:c=pink:a=0.30",
             "-af", "lowpass=f=900,afade=t=in:d=1.05,afade=t=out:st=1.05:d=0.15",
             "-ac", "1", str(riser)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and riser.exists():
            result["riser"] = riser.name
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=55:duration=0.5",
             "-af", "afade=t=out:st=0.08:d=0.42,volume=1.6", "-ac", "1", str(sub)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and sub.exists():
            result["sub_impact"] = sub.name
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
    bridge: str = "",
    bridge_voice: Path | None = None,
    bridge_words: list | None = None,
    background: Path | None = None,
    backgrounds: list | None = None,
    silence_drop_sec: float = 0.0,
    anim_seed: int = 0,
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

    An OPTIONAL 4th scene — the Bridge, rendered between Hook and Quote —
    is enabled by passing non-empty ``bridge`` text (with ``bridge_voice``/
    ``bridge_words`` for VO + word-timed animation). When ``bridge`` is falsy
    the payload is byte-for-byte identical to the pre-Bridge shape: no
    top-level ``bridge`` key, and no ``"bridge"`` entries in ``voices``/
    ``voiceDurations``/``wordTimes`` — so existing (bridge-less) reels are
    completely unaffected.

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
    voice_items = [("hook", hook_voice), ("quote", quote_voice), ("cta", cta_voice)]
    if bridge_voice:
        # Only add the "bridge" key when a bridge voice is actually supplied —
        # keeps the no-bridge payload shape byte-for-byte unchanged.
        voices["bridge"] = None
        voice_durations["bridge"] = None
        voice_items.append(("bridge", bridge_voice))
    for key, p in voice_items:
        if p and Path(p).exists():
            p = Path(p)
            nm = _copy_audio(p, f"vo-{key}{p.suffix}")
            if nm:
                voices[key] = nm
                voice_durations[key] = _probe_duration(p)

    if silence_drop_sec > 0 and voice_durations.get("quote") is not None:
        # The Quote VO's leading silence is trimmed and its Sequence starts
        # `silence_drop_sec` after the visual Quote scene begins (see
        # PovReel.tsx `dropFrames`). Reporting the probed (trimmed) length
        # alone under-sizes the Quote scene window in sceneFrames() — the
        # narration then ends ~ (drop - PAD) late, overlapping CtaVO and
        # escaping the duck span. Padding the reported duration by the drop
        # makes the Quote window absorb it, same as every other scene.
        voice_durations["quote"] = voice_durations["quote"] + silence_drop_sec

    music_name: str | None = None
    if music_path and Path(music_path).exists():
        mp = Path(music_path)
        music_name = _copy_audio(mp, f"music{mp.suffix}")

    # Optional FLUX background image, copied next to the bridge for staticFile().
    bg_name: str | None = None
    bg_duration: float | None = None
    if background and Path(background).exists():
        bp = Path(background)
        bg_name = _copy_audio(bp, f"bg{bp.suffix}")   # _copy_audio copies any file
        if bp.suffix.lower() in (".mp4", ".webm", ".mov", ".m4v"):
            bg_duration = _probe_duration(bp)         # lets Remotion <Loop> it

    # Multi-clip cinematic background: ≥2 usable clips replace the single
    # `background` key with `backgrounds`/`backgroundDurationsSec` lists so
    # Remotion can cut between them. 0-1 clips leaves the legacy single-clip
    # payload above untouched.
    bg_names, bg_durs = [], []
    if backgrounds and len([b for b in backgrounds if b and Path(b).exists()]) >= 2:
        for i, b in enumerate(backgrounds):
            b = Path(b)
            if not b.exists():
                continue
            nm = _copy_audio(b, f"bg{i}{b.suffix}")
            if nm:
                bg_names.append(nm)
                bg_durs.append(_probe_duration(b) or 0.0)

    beats: list[float] = []
    if quote_voice and Path(quote_voice).exists():
        try:
            beats = beat_sync.detect_beats(Path(quote_voice))
        except Exception as e:  # pragma: no cover - defensive
            print(f"  [remotion] beat detection failed ({e}) — reel plays un-synced")
            beats = []
    # Acoustic detection returns nothing on short spoken clips (ebur128 fallback,
    # librosa excluded). Derive emphasis beats from the quote word timings so the
    # impact SFX + camera punches still fire, synced to the narration.
    if not beats and quote_words:
        beats = _emphasis_beats(quote_words)
        if beats:
            print(f"  [remotion] no acoustic beats — using {len(beats)} "
                  f"emphasis beat(s) from quote word timing")

    sfx = _synth_sfx(bridge_path.parent)

    word_times: dict[str, list] = {
        "hook": hook_words or [],
        "quote": quote_words or [],
        "cta": cta_words or [],
    }
    if bridge_words:
        word_times["bridge"] = bridge_words

    # Apply word classification to all wordTimes lists
    word_times = {k: classify_words(v) for k, v in word_times.items()}

    payload = {
        "hook": hook or "",
        "quote": quote or "",
        "attribution": attribution or "",
        "cta": cta or "",
        "mood": mood,
        "duration": round(float(duration), 3),
        "fps": int(fps),
        "animSeed": int(anim_seed),
        "beats": beats,
        "voices": voices,
        "voiceDurations": voice_durations,
        "wordTimes": word_times,
    }
    if bridge:
        payload["bridge"] = bridge
    if music_name:
        payload["music"] = music_name
    if bg_name:
        payload["background"] = bg_name
        if bg_duration:
            payload["backgroundDurationSec"] = bg_duration
    if bg_names:
        payload["backgrounds"] = bg_names
        payload["backgroundDurationsSec"] = bg_durs
        payload.pop("background", None)
        payload.pop("backgroundDurationSec", None)
    if silence_drop_sec > 0:
        payload["silenceDropSec"] = round(float(silence_drop_sec), 3)
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
    timeout: int = 1800,  # 60s story reels need ~10-20min of OffthreadVideo frames
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    music_path: Path | None = None,
    hook_words: list | None = None,
    quote_words: list | None = None,
    cta_words: list | None = None,
    bridge: str = "",
    bridge_voice: Path | None = None,
    bridge_words: list | None = None,
    background: Path | None = None,
    backgrounds: list | None = None,
    silence_drop_sec: float = 0.0,
    anim_seed: int = 0,
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
    bridge_file = write_bridge_file(
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
        bridge=bridge,
        bridge_voice=bridge_voice,
        bridge_words=bridge_words,
        background=background,
        backgrounds=backgrounds,
        silence_drop_sec=silence_drop_sec,
        anim_seed=anim_seed,
    )

    # 2. Invoke the Remotion CLI. --props takes a path to the JSON bridge file.
    cmd = [
        "npx",
        "remotion",
        "render",
        ENTRY_POINT,
        COMPOSITION_ID,
        str(output_path),
        "--timeout=120000",
        f"--props={bridge_file}",
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
