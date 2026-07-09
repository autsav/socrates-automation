"""
Edge-TTS Voiceover Engine — free, no-API-key fallback for OpenAI TTS.

Wraps the `edge-tts` CLI (https://github.com/rany2/edge-tts), a client for
Microsoft Edge's free Read Aloud service. No API key required — this exists
purely as a zero-cost fallback for src/audio/voiceover.py's OpenAI-based
generation, so pipeline.py never has to skip voiceover entirely just because
OPENAI_API_KEY is unset or the OpenAI call failed.

Requires the CLI: pip install edge-tts
"""

import subprocess
from pathlib import Path

# Mood -> edge-tts voice. Same gravitas rationale as voiceover.VOICE_MAP:
# deep, measured male voices read as authoritative/wise for stoic philosophy;
# reserve the more energetic voice for epic_warrior.
VOICE_MAP = {
    "calm_stoic":         "en-US-DavisNeural",
    "cinematic_hopeful":  "en-US-EricNeural",
    "dark_philosophical": "en-US-ChristopherNeural",
    "dramatic_ancient":   "en-GB-ThomasNeural",
    "epic_warrior":       "en-US-GuyNeural",
    "mystical_greek":     "en-GB-RyanNeural",
    "stark_minimal":      "en-US-TonyNeural",
}

DEFAULT_VOICE = "en-US-ChristopherNeural"


def get_voice_for_mood(mood: str) -> str:
    """Return the best edge-tts voice for a given mood."""
    return VOICE_MAP.get(mood, DEFAULT_VOICE)


def generate_scene_voiceover_edge_tts(text: str, voice: str, output_path: Path) -> bool:
    """
    Generate voiceover for a single scene via the edge-tts CLI.
    Trims text if too long, same limit as the OpenAI backend. Returns True on
    success.
    """
    if len(text) > 300:
        text = text[:297] + "..."
    text = text.replace("—", "-").replace("“", '"').replace("”", '"')

    try:
        result = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text,
             "--write-media", str(output_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"  [edge-tts] Saved {output_path.name} ({size_kb:.0f} KB)")
            return True
        print(f"  [edge-tts] Failed: {result.stderr[:200]}")
        return False
    except FileNotFoundError:
        print("  [edge-tts] Not installed. Install: pip install edge-tts")
        return False
    except Exception as e:
        print(f"  [edge-tts] Error: {e}")
        return False


def prepare_reel_voiceover_edge_tts(
    hook_text: str,
    quote_text: str,
    cta_text: str,
    mood: str,
    output_dir: str | Path,
    timestamp: str,
) -> dict:
    """
    Generate all 3 voiceover tracks for a Reel using edge-tts.

    Returns the same shape as voiceover.prepare_reel_voiceover — a drop-in
    fallback for any caller that already handles that dict (e.g. reel_composer).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    voice = get_voice_for_mood(mood)
    print(f"  [edge-tts] Using voice '{voice}' for mood '{mood}'")

    hook_path = out_dir / f"voice_hook_{timestamp}.mp3"
    quote_path = out_dir / f"voice_quote_{timestamp}.mp3"
    cta_path = out_dir / f"voice_cta_{timestamp}.mp3"

    hook_ok = generate_scene_voiceover_edge_tts(hook_text, voice, hook_path)
    quote_ok = generate_scene_voiceover_edge_tts(quote_text, voice, quote_path)
    cta_ok = generate_scene_voiceover_edge_tts(cta_text, voice, cta_path)

    return {
        "hook_voice": hook_path if hook_ok else None,
        "quote_voice": quote_path if quote_ok else None,
        "cta_voice": cta_path if cta_ok else None,
        "voice": voice,
    }


def edge_tts_available() -> bool:
    """Check whether the edge-tts CLI is installed (best-effort, no network)."""
    try:
        result = subprocess.run(["edge-tts", "--help"],
                                capture_output=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
