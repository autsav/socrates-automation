"""
Voiceover Generator — creates spoken narration for each Reel scene.

Backends:
  1. OpenAI TTS (default) — excellent quality, ~$0.015/min
  2. Local fallback — silent mode if no API key

Generates 3 MP3 files per Reel:
  - hook_voice.mp3    (reads the hook text)
  - quote_voice.mp3   (reads the quote text)
  - cta_voice.mp3     (reads the CTA text)
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import requests
from pathlib import Path
from typing import Literal

# Mood → OpenAI voice mapping
# Research: deep baritone voices (echo, onyx) signal authority, wisdom, trust.
# Morgan Freeman effect: low pitch + resonant formants + measured pace = gravitas.
# Default ALL stoic moods to "echo" (Freeman-esque baritone).
# Reserve "onyx" only for epic_warrior when maximum aggression/power needed.
# Avoid bright/approachable voices (nova, shimmer, fable) — philosophy needs weight.
VOICE_MAP = {
    "calm_stoic":         "echo",    # deep, authoritative, contemplative
    "cinematic_hopeful":  "echo",    # aspirational but still weighty
    "dark_philosophical": "echo",    # the darkest, most resonant
    "dramatic_ancient":   "echo",    # history-channel narrator gravitas
    "epic_warrior":       "onyx",    # maximum power, commanding
    "mystical_greek":     "echo",    # clean but deep, not bright
    "stark_minimal":      "echo",    # every word lands with weight
}

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"


def _tts_openai(
    text: str,
    voice: str,
    api_key: str,
    output_path: Path,
    model: str = "tts-1-hd",
) -> bool:
    """
    Generate speech using OpenAI TTS API.
    Returns True on success.
    """
    try:
        resp = requests.post(
            OPENAI_TTS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": "mp3",
            },
            timeout=60,
        )
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        size_kb = output_path.stat().st_size / 1024
        logger.info(f"  [voiceover] ✅ Saved {output_path.name} ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        logger.info(f"  [voiceover] OpenAI TTS failed: {e}")
        return False


def get_voice_for_mood(mood: str) -> str:
    """Return the best OpenAI voice for a given mood."""
    return VOICE_MAP.get(mood, "alloy")


def generate_scene_voiceover(
    text: str,
    voice: str,
    api_key: str,
    output_path: Path,
) -> bool:
    """
    Generate voiceover for a single scene.
    Trims text if too long for the scene.
    """
    # Limit text length — TTS quality drops and costs rise with very long text
    if len(text) > 300:
        text = text[:297] + "..."

    # Clean text for better TTS
    text = text.replace("—", "-").replace("“", '"').replace("”", '"')

    return _tts_openai(text, voice, api_key, output_path)


def prepare_reel_voiceover(
    hook_text: str,
    quote_text: str,
    cta_text: str,
    mood: str,
    api_key: str,
    output_dir: str | Path,
    timestamp: str,
) -> dict:
    """
    Generate all 3 voiceover tracks for a Reel.

    Returns dict with:
        - hook_voice: Path or None
        - quote_voice: Path or None
        - cta_voice: Path or None
        - voice: str (which voice was used)
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    voice = get_voice_for_mood(mood)
    logger.info(f"  [voiceover] Using voice '{voice}' for mood '{mood}'")

    hook_path = out_dir / f"voice_hook_{timestamp}.mp3"
    quote_path = out_dir / f"voice_quote_{timestamp}.mp3"
    cta_path = out_dir / f"voice_cta_{timestamp}.mp3"

    hook_ok = generate_scene_voiceover(hook_text, voice, api_key, hook_path)
    quote_ok = generate_scene_voiceover(quote_text, voice, api_key, quote_path)
    cta_ok = generate_scene_voiceover(cta_text, voice, api_key, cta_path)

    return {
        "hook_voice": hook_path if hook_ok else None,
        "quote_voice": quote_path if quote_ok else None,
        "cta_voice": cta_path if cta_ok else None,
        "voice": voice,
    }


def voiceover_available(api_key: str) -> bool:
    """Check if voiceover can be generated (has API key)."""
    return bool(api_key)


if __name__ == "__main__":
    import sys
    import os

    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        logger.info("Set OPENAI_API_KEY env var to generate voiceovers.")
        sys.exit(1)

    text = sys.argv[1] if len(sys.argv) > 1 else "The unexamined life is not worth living."
    voice = sys.argv[2] if len(sys.argv) > 2 else "alloy"
    out = Path("output") / "test_voiceover.mp3"

    ok = generate_scene_voiceover(text, voice, key, out)
    if ok:
        logger.info(f"Generated: {out}")
    else:
        logger.error("Failed")
