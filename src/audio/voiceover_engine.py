"""
Voiceover Enhancement — emotional narration with prosody control.

Enhances the existing voiceover pipeline with:
  - Emotion-tagged scripts (whispered, intense, calm, reflective)
  - SSML-like prosody hints for OpenAI TTS
  - Pacing control: slow/medium/fast per scene
  - Dramatic pauses and emphasis markers
  - Multi-voice casting (onyx=deep, nova=warm, echo=calm, shimmer=bright)

Usage:
    from src.audio.voiceover_engine import VoiceoverEngine
    vo = VoiceoverEngine(api_key="sk-...")
    script = vo.build_script(
        quote="Know thyself.",
        hook_text="This will change everything.",
        mood="dark_philosophical",
        style="intense",
    )
    audio_path = vo.speak(script, voice="onyx")
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import re
import random
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ProsodyConfig:
    """Voice characteristics for a scene."""
    speed: str = "medium"        # slow | medium | fast
    pitch: str = "normal"        # low | normal | high
    emotion: str = "neutral"     # whispered | intense | calm | reflective | urgent
    pause_after: float = 0.5    # seconds pause after line


class VoiceoverEngine:
    """
    Build emotionally-tagged voiceover scripts and generate speech.
    """

    # OpenAI TTS voice characteristics
    VOICES = {
        "onyx": {"description": "Deep, authoritative, cinematic", "gender": "male"},
        "nova": {"description": "Warm, smooth, empathetic", "gender": "female"},
        "echo": {"description": "Calm, measured, philosophical", "gender": "male"},
        "shimmer": {"description": "Bright, clear, hopeful", "gender": "female"},
        "fable": {"description": "British, storyteller, wise", "gender": "male"},
        "alloy": {"description": "Neutral, versatile, balanced", "gender": "neutral"},
    }

    # Mood → recommended voice mapping
    MOOD_VOICES = {
        "dark_philosophical": "onyx",
        "dramatic_ancient": "fable",
        "cinematic_hopeful": "nova",
        "stark_minimal": "echo",
        "epic_warrior": "onyx",
        "mystical_greek": "shimmer",
        "calm_stoic": "echo",
    }

    # Emotion markers → SSML-like hints (OpenAI TTS doesn't fully support SSML,
    # but we can simulate with text formatting)
    EMOTION_MARKERS = {
        "whispered": ("(whispers) ", "..."),
        "intense": ("", "!"),
        "calm": ("", "."),
        "reflective": ("(reflectively) ", "..."),
        "urgent": ("", "!"),
    }

    # Pacing: slow = more pauses, fast = fewer
    PACE_HINTS = {
        "slow": ["...", "... breathe...", "... pause..."],
        "medium": ["...", ""],
        "fast": ["", "", ""],
    }

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def build_script(
        self,
        quote: str,
        hook_text: str = "",
        cta_text: str = "",
        mood: str = "dark_philosophical",
        style: str = "intense",
    ) -> dict[str, str]:
        """
        Build an emotionally-tagged 3-scene voiceover script.
        Returns dict with hook_voice, quote_voice, cta_voice text.
        """
        configs = self._scene_configs(mood, style)

        scripts = {}

        # Hook scene script
        if hook_text:
            hook_script = self._format_line(
                hook_text,
                configs["hook"],
                prefix=configs["hook"].emotion != "neutral",
            )
            scripts["hook_voice"] = hook_script

        # Quote scene script
        quote_script = self._format_quote(
            quote,
            configs["quote"],
        )
        scripts["quote_voice"] = quote_script

        # CTA scene script
        if cta_text:
            cta_script = self._format_line(
                cta_text,
                configs["cta"],
                prefix=False,
            )
            scripts["cta_voice"] = cta_script

        # Point 16: Apply strategic silence to all scenes
        scripts = self.add_strategic_silence(scripts)

        return scripts

    def _scene_configs(self, mood: str, style: str) -> dict[str, ProsodyConfig]:
        """Determine prosody for each scene based on mood and style."""
        if style == "intense":
            return {
                "hook": ProsodyConfig(speed="fast", emotion="urgent", pause_after=0.3),
                "quote": ProsodyConfig(speed="medium", emotion="intense", pause_after=0.8),
                "cta": ProsodyConfig(speed="fast", emotion="urgent", pause_after=0.2),
            }
        elif style == "calm":
            return {
                "hook": ProsodyConfig(speed="slow", emotion="calm", pause_after=0.6),
                "quote": ProsodyConfig(speed="slow", emotion="reflective", pause_after=1.0),
                "cta": ProsodyConfig(speed="medium", emotion="calm", pause_after=0.5),
            }
        elif style == "whispered":
            return {
                "hook": ProsodyConfig(speed="slow", emotion="whispered", pause_after=0.5),
                "quote": ProsodyConfig(speed="slow", emotion="whispered", pause_after=1.2),
                "cta": ProsodyConfig(speed="slow", emotion="whispered", pause_after=0.4),
            }
        else:  # balanced default
            mood_configs = {
                "dark_philosophical": {
                    "hook": ProsodyConfig(speed="medium", emotion="urgent"),
                    "quote": ProsodyConfig(speed="slow", emotion="intense"),
                    "cta": ProsodyConfig(speed="medium", emotion="urgent"),
                },
                "cinematic_hopeful": {
                    "hook": ProsodyConfig(speed="medium", emotion="calm"),
                    "quote": ProsodyConfig(speed="slow", emotion="reflective"),
                    "cta": ProsodyConfig(speed="medium", emotion="calm"),
                },
                "epic_warrior": {
                    "hook": ProsodyConfig(speed="fast", emotion="urgent"),
                    "quote": ProsodyConfig(speed="medium", emotion="intense"),
                    "cta": ProsodyConfig(speed="fast", emotion="urgent"),
                },
                "calm_stoic": {
                    "hook": ProsodyConfig(speed="slow", emotion="calm"),
                    "quote": ProsodyConfig(speed="slow", emotion="reflective"),
                    "cta": ProsodyConfig(speed="slow", emotion="calm"),
                },
                "mystical_greek": {
                    "hook": ProsodyConfig(speed="medium", emotion="whispered"),
                    "quote": ProsodyConfig(speed="slow", emotion="reflective"),
                    "cta": ProsodyConfig(speed="medium", emotion="whispered"),
                },
            }
            return mood_configs.get(mood, mood_configs["dark_philosophical"])

    def _format_line(self, text: str, config: ProsodyConfig, prefix: bool = True) -> str:
        """Format a single line with emotion markers and pacing."""
        marker = self.EMOTION_MARKERS.get(config.emotion, ("", ""))
        prefix_str = marker[0] if prefix else ""
        suffix = marker[1]

        # Add pacing pauses
        if config.speed == "slow":
            text = text.replace(".", "... ")
            text = text.replace(",", ", ")
        elif config.speed == "fast":
            text = re.sub(r"\.{3}", ".", text)

        return f"{prefix_str}{text}{suffix}"

    def _format_quote(self, quote: str, config: ProsodyConfig) -> str:
        """Format a quote with emotional weight and strategic silence."""
        marker = self.EMOTION_MARKERS.get(config.emotion, ("", ""))
        prefix = marker[0]

        # Break long quotes into breath units with pauses
        words = quote.split()
        if len(words) > 15:
            # Find a natural breakpoint around the middle
            mid = len(words) // 2
            # Prefer breaking at punctuation or conjunction
            for i in range(mid - 3, mid + 3):
                if i > 0 and i < len(words):
                    if words[i].endswith((",", ";", ":")):
                        mid = i + 1
                        break
            first_half = " ".join(words[:mid])
            second_half = " ".join(words[mid:])
            # Point 16: 0.5s silence before punchline (second half)
            silence_before_punchline = "... "
            formatted = f"{prefix}{first_half}{silence_before_punchline}{second_half}"
        else:
            formatted = f"{prefix}{quote}"

        if config.speed == "slow":
            formatted = formatted.replace(".", "... ")

        # Point 16: 1s pause after quote for impact (appended to end of quote_voice)
        formatted += "..."

        return formatted

    def add_strategic_silence(
        self,
        script: dict[str, str],
        hook_pause: float = 0.3,
        quote_post_pause: float = 1.0,
    ) -> dict[str, str]:
        """
        Point 16: Insert strategic silence gaps into a voiceover script.
        hook_pause: silence after hook (0.3s) — short beat before quote
        quote_post_pause: silence after quote (1.0s) — impact sink-in time
        Implemented via trailing ellipsis/pause markers that TTS models honour.
        """
        result = dict(script)
        if "hook_voice" in result:
            # Brief pause after hook — let it land before quote starts
            if not result["hook_voice"].endswith("..."):
                result["hook_voice"] = result["hook_voice"].rstrip(".") + "..."
        if "quote_voice" in result:
            # Ensure trailing pause after quote
            text = result["quote_voice"]
            if not text.endswith("..."):
                result["quote_voice"] = text.rstrip(".") + "... " + "." * int(quote_post_pause * 2)
        return result

    def pick_voice(self, mood: str, preference: str = "") -> str:
        """
        Pick the best OpenAI TTS voice for the mood.
        Override with preference if provided.
        """
        if preference and preference in self.VOICES:
            return preference
        return self.MOOD_VOICES.get(mood, "onyx")

    def generate_all(
        self,
        hook_text: str,
        quote: str,
        cta_text: str,
        mood: str,
        api_key: str,
        output_dir: str = "output",
        timestamp: str = "",
        style: str = "intense",
    ) -> dict | None:
        """
        Generate all 3 voiceover audio files.
        Returns dict with paths or None if generation fails.
        """
        if not api_key:
            return None

        scripts = self.build_script(quote, hook_text, cta_text, mood, style)
        voice = self.pick_voice(mood)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {}
        for key, script_text in scripts.items():
            if not script_text:
                continue
            output_path = output_dir / f"{key}_{timestamp or 'tmp'}.mp3"
            try:
                self._generate_speech(script_text, voice, api_key, output_path)
                result[key] = str(output_path)
            except Exception as e:
                logger.info(f"  [voiceover] Failed to generate {key}: {e}")

        return result if result else None

    def _generate_speech(self, text: str, voice: str, api_key: str, output_path: Path):
        """Call OpenAI TTS API to generate speech."""
        import requests

        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(resp.content)

        logger.info(f"  [voiceover] Generated {output_path.name} ({output_path.stat().st_size / 1024:.0f} KB)")

    @classmethod
    def demo_voices(cls) -> list[str]:
        """Return available voice IDs for testing."""
        return list(cls.VOICES.keys())

    @classmethod
    def voice_description(cls, voice_id: str) -> str:
        """Get human-readable description of a voice."""
        return cls.VOICES.get(voice_id, {}).get("description", "Unknown")


# ── Convenience exports ────────────────────────────────────────────────────────

def generate_enhanced_voiceover(
    hook_text: str,
    quote: str,
    cta_text: str,
    mood: str,
    api_key: str,
    output_dir: str = "output",
    timestamp: str = "",
    style: str = "intense",
) -> dict | None:
    """One-shot enhanced voiceover generation."""
    engine = VoiceoverEngine(api_key=api_key)
    return engine.generate_all(
        hook_text=hook_text,
        quote=quote,
        cta_text=cta_text,
        mood=mood,
        api_key=api_key,
        output_dir=output_dir,
        timestamp=timestamp,
        style=style,
    )
