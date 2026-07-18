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
import requests
import json
import tempfile
from pathlib import Path
from typing import Optional

# ElevenLabs API endpoints
ELEVENLABS_API = "https://api.elevenlabs.io/v1"

# Pre-selected voices for philosophy content
VOICES = {
    "sage":      "pNIncy4yVsqPhqIdc4Kc",   # Adam — deep, authoritative, "wise elder"
    "intense":   "TxGEqnHWrfWFTfWB9MjX",   # Josh — younger, intense, confrontational
    "contemplative": "ErXw8Y8QH8n2Zn2l5J8h", # Sam — thoughtful, philosophical
}

# Voice settings optimized for narration (not dialogue)
DEFAULT_SETTINGS = {
    "stability": 0.35,        # Lower = more expressive, less monotone
    "similarity_boost": 0.75,  # Higher = closer to original voice
    "style": 0.0,              # 0 = neutral, 1 = exaggerated
    "use_speaker_boost": True,  # Enhances voice clarity
}

# Mood -> voice mapping
MOOD_VOICES = {
    "calm_stoic":         "sage",
    "cinematic_hopeful":  "contemplative",
    "dark_philosophical": "intense",
    "dramatic_ancient":   "sage",
    "epic_warrior":       "intense",
    "mystical_greek":     "contemplative",
    "stark_minimal":      "sage",
}

# Reel narration: use the "intense" voice for confrontational content
# (matches the new controversy engine style)
REEL_VOICE = "intense"


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
    if not api_key:
        return None

    voice_id = VOICES.get(voice, voice)
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    output_path = Path(output_path) if output_path else Path(tempfile.mktemp(suffix=".mp3"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(text) > 500:
        text = text[:497] + "..."

    try:
        response = requests.post(
            f"{ELEVENLABS_API}/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",  # Fast, high-quality, multilingual
                "voice_settings": settings,
            },
            timeout=30,
        )
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

        if not output_path.exists() or output_path.stat().st_size == 0:
            return None

        size_kb = output_path.stat().st_size / 1024
        print(f"  [elevenlabs] Saved {output_path.name} ({size_kb:.0f} KB)")
        return output_path

    except Exception as e:
        print(f"  [elevenlabs] Error: {e}")
        return None


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

    # Generate estimated word timings for animation sync
    duration = _get_audio_duration(result)
    words = _estimate_word_timings(text, duration)

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
) -> dict:
    """Generate all 3 voiceover tracks for a Reel using ElevenLabs.

    Returns the same dict shape as edge_tts_engine.prepare_reel_voiceover_edge_tts
    so it's a drop-in replacement.
    """
    from src.audio.edge_tts_engine import parse_word_srt, _write_word_srt

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    voice = REEL_VOICE
    print(f"  [elevenlabs] Using voice '{voice}' for mood '{mood}'")

    hook_path = out_dir / f"voice_hook_{timestamp}.mp3"
    quote_path = out_dir / f"voice_quote_{timestamp}.mp3"
    cta_path = out_dir / f"voice_cta_{timestamp}.mp3"

    # A cold-open arc has no hook — skip its synthesis (and its API cost).
    hook_ok = bool(hook_text) and generate_scene_voiceover(hook_text, voice, hook_path, api_key)
    quote_ok = generate_scene_voiceover(quote_text, voice, quote_path, api_key)
    cta_ok = generate_scene_voiceover(cta_text, voice, cta_path, api_key)

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