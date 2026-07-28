"""Shared reel-data builder — one canonical dict for both Remotion and HyperFrames.

Extracted from ``remotion_reel.py::write_bridge_file`` so adding a field here
flows to both renderers automatically.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from src.utils.logger import get_logger
from src.video import beat_sync
from src.video.word_classes import classify_words

logger = get_logger(__name__)

SUPPORTED_MOODS = (
    "dark_philosophical",
    "dramatic_ancient",
    "cinematic_hopeful",
    "stark_minimal",
    "epic_warrior",
    "mystical_greek",
    "calm_stoic",
)


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


def _emphasis_beats(words: list | None, max_beats: int = 2, min_gap: float = 1.2) -> list[float]:
    """Derive impact-SFX beat times from per-word timings."""
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
    candidates.sort(reverse=True)
    picked: list[float] = []
    for _dur, t in candidates:
        if all(abs(t - p) >= min_gap for p in picked):
            picked.append(t)
        if len(picked) >= max_beats:
            break
    return sorted(picked)


def _synth_sfx(dest_dir: Path) -> dict | None:
    """Synthesize whoosh + impact + riser + sub_impact SFX with ffmpeg."""
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
            result["whoosh"] = str(whoosh)
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=85:duration=0.22",
             "-af", "afade=t=out:st=0.03:d=0.19", "-ac", "1", str(impact)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and impact.exists():
            result["impact"] = str(impact)
    except Exception:
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
            result["riser"] = str(riser)
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=55:duration=0.5",
             "-af", "afade=t=out:st=0.08:d=0.42,volume=1.6", "-ac", "1", str(sub)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and sub.exists():
            result["sub_impact"] = str(sub)
    except Exception:
        pass
    return result or None


def build_reel_data(
    hook: str = "",
    quote: str = "",
    attribution: str = "",
    cta: str = "",
    mood: str = "dark_philosophical",
    duration: float = 10.5,
    fps: int = 30,
    hook_voice: Path | None = None,
    quote_voice: Path | None = None,
    cta_voice: Path | None = None,
    bridge_voice: Path | None = None,
    music_path: Path | None = None,
    hook_words: list | None = None,
    quote_words: list | None = None,
    cta_words: list | None = None,
    bridge: str = "",
    bridge_words: list | None = None,
    background: Path | None = None,
    backgrounds: list | None = None,
    silence_drop_sec: float = 0.0,
    anim_seed: int = 0,
) -> dict:
    """Return the canonical reel-data dict shared by Remotion and HyperFrames.

    Does NOT copy files — callers handle their own asset staging.
    """
    if mood not in SUPPORTED_MOODS:
        mood = SUPPORTED_MOODS[0]

    voices: dict[str, str | None] = {"hook": None, "quote": None, "cta": None}
    voice_durations: dict[str, float | None] = {"hook": None, "quote": None, "cta": None}
    voice_items = [("hook", hook_voice), ("quote", quote_voice), ("cta", cta_voice)]
    if bridge_voice:
        voices["bridge"] = None
        voice_durations["bridge"] = None
        voice_items.append(("bridge", bridge_voice))
    for key, p in voice_items:
        if p and Path(p).exists():
            voices[key] = str(p)
            voice_durations[key] = _probe_duration(Path(p))

    if silence_drop_sec > 0 and voice_durations.get("quote") is not None:
        voice_durations["quote"] = voice_durations["quote"] + silence_drop_sec

    music_name: str | None = None
    if music_path and Path(music_path).exists():
        music_name = str(Path(music_path))

    bg_name: str | None = None
    bg_duration: float | None = None
    if background and Path(background).exists():
        bg_name = str(Path(background))
        if Path(background).suffix.lower() in (".mp4", ".webm", ".mov", ".m4v"):
            bg_duration = _probe_duration(Path(background))

    bg_names, bg_durs = [], []
    if backgrounds and len([b for b in backgrounds if b and Path(b).exists()]) >= 2:
        for i, b in enumerate(backgrounds):
            b = Path(b)
            if not b.exists():
                continue
            bg_names.append(str(b))
            bg_durs.append(_probe_duration(b) or 0.0)

    beats: list[float] = []
    if quote_voice and Path(quote_voice).exists():
        try:
            beats = beat_sync.detect_beats(Path(quote_voice))
        except Exception as e:  # pragma: no cover
            logger.info(f"  [reel-data] beat detection failed ({e}) — reel plays un-synced")
            beats = []
    if not beats and quote_words:
        beats = _emphasis_beats(quote_words)
        if beats:
            logger.info(f"  [reel-data] no acoustic beats — using {len(beats)} emphasis beat(s)")

    sfx = _synth_sfx(Path("."))  # caller should relocate files if needed

    word_times: dict[str, list] = {
        "hook": hook_words or [],
        "quote": quote_words or [],
        "cta": cta_words or [],
    }
    if bridge_words:
        word_times["bridge"] = bridge_words
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

    return payload
