"""Per-scene delivery direction for ElevenLabs narration (spec 1).
One flat read is the tell of TTS; profiles give each scene a performance:
hook attacks, the story builds urgency, the quote lands slow and low."""
import re
import shutil
import subprocess
from pathlib import Path

# Overrides merged over elevenlabs_engine.DEFAULT_SETTINGS by the caller.
# `speed` is honored by eleven_turbo_v2_5 (the engine's model_id) and ignored
# harmlessly on models that don't support it. The hook attacks faster (+12%),
# the quote slows for gravitas (-8%) — compounding the ~5% pitch-down from
# apply_gravitas. Lower hook stability = more expressive/urgent.
_PROFILES = {
    "hook":  {"stability": 0.18, "style": 0.62, "speed": 1.12},   # intense, fast attack
    "quote": {"stability": 0.72, "style": 0.05, "speed": 0.92},   # slow gravitas
    "cta":   {"stability": 0.40, "style": 0.30, "speed": 1.0},    # direct, close
}
_BRIDGE_BASE_STABILITY = 0.45
_BRIDGE_STEP = 0.05          # each chapter gets more urgent
_BRIDGE_FLOOR = 0.18


def delivery_profile(scene: str, chapter_index: int | None = None) -> dict:
    """Voice-settings overrides for a scene. Unknown scene -> {} (defaults)."""
    if scene == "bridge":
        idx = chapter_index or 0
        stability = max(_BRIDGE_FLOOR, _BRIDGE_BASE_STABILITY - _BRIDGE_STEP * idx)
        return {"stability": round(stability, 2), "style": 0.4}
    return dict(_PROFILES.get(scene, {}))


def insert_chapter_breaks(text: str, group_size: int = 3) -> str:
    """Insert a 0.4s break tag after every `group_size` sentences — the
    chapter turns of a story beat. ElevenLabs renders <break> as silence."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    if len(parts) <= group_size:
        return text
    out = []
    for i, sentence in enumerate(parts):
        out.append(sentence)
        if (i + 1) % group_size == 0 and i + 1 < len(parts):
            out.append('<break time="0.4s" />')
    return " ".join(out)


def apply_gravitas(path: Path) -> bool:
    """~5% pitch-down on the quote VO (lower pitch narrows the AI-vs-human
    gap — peer-reviewed finding). Skips files whose sibling SRT contains
    <break> tags (pitch shift would corrupt explicit pause timing).
    In-place; best-effort; False on failure."""
    try:
        path = Path(path)
        if not path.exists() or not shutil.which("ffmpeg"):
            return False
        srt = path.with_suffix(".srt")
        if srt.exists() and "<break" in srt.read_text(errors="ignore"):
            return False
        tmp = path.with_suffix(".grav" + path.suffix)
        # asetrate lowers pitch AND speed; atempo restores duration.
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(path),
             "-af", "asetrate=44100*0.95,aresample=44100,atempo=1.0526",
             str(tmp)],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
            return False
        tmp.replace(path)
        return True
    except Exception:  # noqa: BLE001 - direction is optional, never fatal
        return False
