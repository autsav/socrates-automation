"""ElevenLabs emotion-tag handling for voiceover copy.

ElevenLabs native audio tags rendered into spoken performance:
  [sighs] [dryly] [sarcastically] [emphatic] [calmly] [pause]

[pause] is mapped to <break time="0.5s" /> (ElevenLabs renders break tags
as actual silence); other tags are passed through literal so the TTS model
interprets them.
"""
from __future__ import annotations

import re
from src.utils.logger import get_logger

logger = get_logger(__name__)

EMOTION_TAGS = frozenset({
    "[sighs]", "[dryly]", "[sarcastically]", "[emphatic]", "[calmly]", "[pause]",
})

_PAUSE_TAG_RE = re.compile(r"\[pause\]")
_BREAK_RE = re.compile(r'(<break[^>]*?/>)(\s*<break[^>]*?/>)+')


def sanitize_for_tts(text: str) -> str:
    """Convert [pause] -> <break time="0.5s" />; leave other tags literal."""
    if not text:
        return text
    return _PAUSE_TAG_RE.sub('<break time="0.5s" />', text)


def expand_chapter_breaks(text: str) -> str:
    """One-shot: [pause] → <break>, then collapse consecutive <break> tags to one."""
    if not text:
        return text
    converted = _PAUSE_TAG_RE.sub('<break time="0.5s" />', text)
    return _BREAK_RE.sub(lambda m: m.group(1), converted)


def tag_count(text: str) -> dict:
    """Diagnostic: count each EMOTION_TAG in text."""
    counts = {tag: 0 for tag in EMOTION_TAGS}
    for tag in EMOTION_TAGS:
        counts[tag] = text.count(tag)
    return counts
