"""ElevenLabs Voiceover Engine — human-quality AI narration.

ElevenLabs produces the most human-sounding TTS available in 2025-2026.
Users cannot tell it apart from a real voice actor in blind tests.

This module replaces edge-tts as the primary voiceover engine for Reels.
edge-tts remains as a zero-cost fallback when ELEVENLABS_API_KEY is not set.

Key advantages over edge-tts:
- Natural breathing, pauses, emphasis
- Emotion control via voice settings
- No robotic cadence
- Users actually watch the full Reel instead of scrolling past

Voice choice: "pNIncy4yVsqPhqIdc4Kc" (Adam) — deep, authoritative narrator.
Alternative: "TxGEqnHWrfWFTfWB9MjX" (Josh) — younger, intense delivery.
Alternative: "ErXw8Y8QH8n2Zn2l5J8h" (Sam) — contemplative, philosophical.
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import base64
import re
import requests
import json
import tempfile
from pathlib import Path
from typing import Optional

# ElevenLabs API endpoints
ELEVENLABS_API = "https://api.elevenlabs.io/v1"

# Pre-selected baritone voices for philosophy content
# IDs verified against this account's /v1/voices listing.
VOICES = {
    # New baritone roster
    "josh":   "TxGEqnHWrfWFTfWB9MjX",  # Josh — younger intense, opt-in for epic_warrior
    "bill":   "pqHfZ75CvOlQylNhV4",   # Bill — wise, mature, balanced (default REEL_VOICE)
    "david":  "onwK4e9ZLuTAKqWW03F9",  # David — British, narrative, contemplative
    # Legacy aliases preserved for back-compat
    "sage":          "pqHfZ75CvOlQylNhV4",   # alias for bill
    "intense":       "TxGEqnHWrfWFTfWB9MjX", # alias for josh
    "contemplative": "onwK4e9ZLuTAKqWW03F9", # alias for david
}

# Voice settings optimized for narration (not dialogue)
DEFAULT_SETTINGS = {
    "stability": 0.35,        # Lower = more expressive, less monotone
    "similarity_boost": 0.75,  # Higher = closer to original voice
    "style": 0.0,              # 0 = neutral, 1 = exaggerated
    "use_speaker_boost": True,  # Enhances voice clarity
}

# Mood -> voice mapping (deep baritone default for gravitas)
MOOD_VOICES = {
    "calm_stoic":         "bill",
    "cinematic_hopeful":  "david",
    "dark_philosophical": "bill",
    "dramatic_ancient":   "bill",
    "epic_warrior":       "josh",
    "mystical_greek":     "david",
    "stark_minimal":      "bill",
}

# Default narration voice — deepest, wisest, most-resonant baritone
REEL_VOICE = "bill"


def _srt_ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def _fmt_srt_ts(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _estimate_word_timings(text: str, total_duration: float) -> list[dict]:
    """Estimate word timings when ElevenLabs doesn't provide them.

    Distributes words evenly across the audio duration with slight
    pauses at punctuation.
    """
    words = text.split()
    if not words or total_duration <= 0:
        return []

    # Average word duration with punctuation pauses
    total_words = len(words)
    base_duration = total_duration / total_words

    timings = []
    current_time = 0.0
    for word in words:
        # Add longer pause after punctuation
        pause = 0.15 if word.endswith((".", ",", "!", "?", ";", ":")) else 0
        word_duration = base_duration + pause
        timings.append({
            "w": word,
            "start": round(current_time, 3),
            "end": round(current_time + word_duration, 3),
        })
        current_time += word_duration

    # Normalize to fit total duration
    if timings and timings[-1]["end"] > total_duration:
        scale = total_duration / timings[-1]["end"]
        for t in timings:
            t["start"] = round(t["start"] * scale, 3)
            t["end"] = round(t["end"] * scale, 3)

    return timings


_BREAK_TAG = re.compile(r"<break\b[^>]*/>")


def _alignment_to_words(text: str, alignment: dict | None) -> list[dict]:
    """Group ElevenLabs character alignment into word timings. The characters
    ARE the spoken text (incl. any break tags); words inside break tags are
    silence markup, not display words. Returns [] on any malformed input."""
    try:
        chars = alignment["characters"]
        starts = alignment["character_start_times_seconds"]
        ends = alignment["character_end_times_seconds"]
        if not chars or len(chars) != len(starts) or len(chars) != len(ends):
            return []
        # Mark index ranges covered by break tags so their chars are skipped.
        joined = "".join(chars)
        skip = [False] * len(chars)
        for m in _BREAK_TAG.finditer(joined):
            for i in range(m.start(), m.end()):
                skip[i] = True
        words, cur, w_start, w_end = [], "", None, None
        for i, ch in enumerate(chars):
            if skip[i]:
                continue
            if ch.isspace():
                if cur:
                    words.append({"w": cur, "start": round(w_start, 3),
                                  "end": round(w_end, 3)})
                    cur, w_start = "", None
                continue
            if not cur:
                w_start = starts[i]
            cur += ch
            w_end = ends[i]
        if cur:
            words.append({"w": cur, "start": round(w_start, 3),
                          "end": round(w_end, 3)})
        return words
    except Exception:  # noqa: BLE001 - timing extras must never kill VO
        return []


def _get_audio_duration(path: Path) -> float:
    """Get audio duration in seconds using ffprobe (best-effort)."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0


def generate_voiceover(
    text: str,
    api_key: str,
    voice: str = REEL_VOICE,
    output_path: Path | str = None,
    settings: dict = None,
) -> Path | None:
    """Generate a single voiceover MP3 via ElevenLabs API.

    Args:
        text: The text to narrate
        api_key: ElevenLabs API key
        voice: Voice key from VOICES dict, or raw voice ID
        output_path: Where to save the MP3. Auto-generated if None.
        settings: Voice settings dict (overrides DEFAULT_SETTINGS)

    Returns:
        Path to the MP3 file, or None on failure.
    """
    # Reset first so a fallback run (or an early return) never inherits a
    # previous call's words.
    generate_voiceover.last_words = []

    if not api_key:
        return None

    voice_id = VOICES.get(voice, voice)
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    output_path = Path(output_path) if output_path else Path(tempfile.mktemp(suffix=".mp3"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Cost guard. Was 500 — which silently truncated 60s story-arc bridges
    # (~1000+ chars) to their first ~90 words. 1500 covers a 185-word story
    # beat; anything longer is a caller bug, not a reel.
    if len(text) > 1500:
        text = text[:1497] + "..."

    body = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",  # Fast, high-quality, multilingual
        "voice_settings": settings,
    }
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    words: list[dict] = []

    try:
        response = requests.post(
            f"{ELEVENLABS_API}/text-to-speech/{voice_id}/with-timestamps",
            headers=headers, json=body, timeout=30)
        response.raise_for_status()
        j = response.json()
        audio = base64.b64decode(j["audio_base64"])
        words = _alignment_to_words(text, j.get("alignment"))
        with open(output_path, "wb") as f:
            f.write(audio)
    except Exception as e:  # noqa: BLE001 - fall back to the plain endpoint
        logger.info(f"  [elevenlabs] with-timestamps unavailable ({e}) — plain endpoint")
        words = []
        try:
            response = requests.post(
                f"{ELEVENLABS_API}/text-to-speech/{voice_id}",
                headers={**headers, "Accept": "audio/mpeg"}, json=body, timeout=30)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(response.content)
        except Exception as e2:
            logger.info(f"  [elevenlabs] Error: {e2}")
            return None

    if not output_path.exists() or output_path.stat().st_size == 0:
        return None

    size_kb = output_path.stat().st_size / 1024
    logger.info(f"  [elevenlabs] Saved {output_path.name} ({size_kb:.0f} KB)")
    generate_voiceover.last_words = words
    return output_path


generate_voiceover.last_words = []


def generate_scene_voiceover(
    text: str,
    voice: str,
    output_path: Path,
    api_key: str,
    settings: dict = None,
) -> bool:
    """Generate voiceover for a single scene. Returns True on success.

    Also writes an estimated word-level SRT for text animation sync.
    """
    result = generate_voiceover(text, api_key, voice, output_path, settings)
    if result is None:
        return False

    # Prefer real ElevenLabs alignment timings; fall back to estimation when
    # unavailable (fallback endpoint used, or malformed alignment).
    real = getattr(generate_voiceover, "last_words", []) or []
    duration = _get_audio_duration(result)
    words = real if real else _estimate_word_timings(text, duration)

    srt_path = result.with_suffix(".srt")
    lines = []
    for i, w in enumerate(words, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_ts(w['start'])} --> {_fmt_srt_ts(w['end'])}")
        lines.append(w["w"])
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8")

    return True


def prepare_reel_voiceover(
    hook_text: str,
    quote_text: str,
    cta_text: str,
    mood: str,
    output_dir: str | Path,
    timestamp: str,
    api_key: str,
    scene_settings: dict[str, dict] | None = None,
) -> dict:
    """Generate all 3 voiceover tracks for a Reel using ElevenLabs.

    Args:
        scene_settings: optional per-scene voice_settings overrides, e.g.
            {"hook": {...}, "quote": {...}, "cta": {...}} (see
            voice_director.delivery_profile). Merged over DEFAULT_SETTINGS by
            generate_voiceover, same as generate_scene_voiceover's own
            `settings` arg. None (default) = current behavior, no overrides.

    Returns the same dict shape as edge_tts_engine.prepare_reel_voiceover_edge_tts
    so it's a drop-in replacement.
    """
    from src.audio.edge_tts_engine import parse_word_srt, _write_word_srt

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    voice = REEL_VOICE
    logger.info(f"  [elevenlabs] Using voice '{voice}' for mood '{mood}'")

    scene_settings = scene_settings or {}
    hook_path = out_dir / f"voice_hook_{timestamp}.mp3"
    quote_path = out_dir / f"voice_quote_{timestamp}.mp3"
    cta_path = out_dir / f"voice_cta_{timestamp}.mp3"

    # A cold-open arc has no hook — skip its synthesis (and its API cost).
    hook_ok = bool(hook_text) and generate_scene_voiceover(
        hook_text, voice, hook_path, api_key, settings=scene_settings.get("hook"))
    quote_ok = generate_scene_voiceover(
        quote_text, voice, quote_path, api_key, settings=scene_settings.get("quote"))
    cta_ok = generate_scene_voiceover(
        cta_text, voice, cta_path, api_key, settings=scene_settings.get("cta"))

    # Parse the SRTs we generated
    hook_words = parse_word_srt(hook_path.with_suffix(".srt")) if hook_ok else []
    quote_words = parse_word_srt(quote_path.with_suffix(".srt")) if quote_ok else []
    cta_words = parse_word_srt(cta_path.with_suffix(".srt")) if cta_ok else []

    return {
        "hook_voice": hook_path if hook_ok else None,
        "quote_voice": quote_path if quote_ok else None,
        "cta_voice": cta_path if cta_ok else None,
        "hook_words": hook_words,
        "quote_words": quote_words,
        "cta_words": cta_words,
        "voice": voice,
    }


def elevenlabs_available(api_key: str = "") -> bool:
    """Check if ElevenLabs is available (API key present)."""
    return bool(api_key)