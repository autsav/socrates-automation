"""
Edge-TTS Voiceover Engine — free, no-API-key fallback for OpenAI TTS.

Wraps the `edge-tts` CLI (https://github.com/rany2/edge-tts), a client for
Microsoft Edge's free Read Aloud service. No API key required — this exists
purely as a zero-cost fallback for src/audio/voiceover.py's OpenAI-based
generation, so pipeline.py never has to skip voiceover entirely just because
OPENAI_API_KEY is unset or the OpenAI call failed.

Requires the package: pip install edge-tts

Uses the edge-tts **Python API** (not the CLI): a single ``Communicate`` stream
per scene writes the MP3 *and* yields per-word ``WordBoundary`` events, which we
persist as a word-level SRT. This gives true word-by-word timings (the CLI only
emits sentence-level cues) and drops the requirement that the ``edge-tts`` binary
be on ``PATH`` — importing the package is enough.
"""

import asyncio
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

# ── Reel narration voice ──────────────────────────────────────────────────────
# One consistent "wise grandfather / teacher" sage voice for all reel narration:
# warm and authoritative, slowed and pitched down for a deep, deliberate,
# Morgan-Freeman-adjacent delivery. Chosen by ear (sample "A2_Andrew_MAX"); see
# docs/superpowers/specs/2026-07-12-reel-narration-voice-design.md.
REEL_VOICE = "en-US-AndrewNeural"
REEL_RATE = "-30%"    # slow, deliberate (default / fallback)
REEL_PITCH = "-14Hz"  # deep bass (default / fallback)

# Narration arc — one sage voice, four deliveries. Flat prosody across scenes
# reads as TTS; an arc reads as a narrator: the hook grabs (closest to natural
# pace), the bridge builds, the QUOTE lands slowest and deepest (the payoff),
# and the CTA lifts back up, warm.
SCENE_PROSODY = {
    "hook":   ("-18%", "-8Hz"),
    "bridge": ("-24%", "-11Hz"),
    "quote":  ("-32%", "-16Hz"),
    "cta":    ("-20%", "-6Hz"),
}


def get_voice_for_mood(mood: str) -> str:
    """Return the best edge-tts voice for a given mood."""
    return VOICE_MAP.get(mood, DEFAULT_VOICE)


def _srt_ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def _fmt_srt_ts(t: float) -> str:
    """Seconds -> SRT timestamp 'HH:MM:SS,mmm' (inverse of _srt_ts)."""
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _write_word_srt(path: Path, words: list[dict]) -> None:
    """Write [{w,start,end}] as a word-level SRT that parse_word_srt round-trips."""
    lines: list[str] = []
    for i, w in enumerate(words, 1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_ts(w['start'])} --> {_fmt_srt_ts(w['end'])}")
        lines.append(str(w["w"]))
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


async def _edge_tts_synth(text: str, voice: str, media_path: Path,
                          rate: str = "+0%", pitch: str = "+0Hz") -> list[dict]:
    """Synthesize ``text`` to ``media_path`` (MP3) via the edge-tts Python API,
    returning per-word timings [{w,start,end}] from WordBoundary events.

    ``rate``/``pitch`` are edge-tts prosody strings (e.g. "-30%" / "-14Hz") used
    to slow and deepen the narration. Offsets/durations arrive in 100-nanosecond
    ticks; divide by 1e7 for seconds.
    """
    import edge_tts  # imported lazily so the module loads even if absent

    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                boundary="WordBoundary")
    words: list[dict] = []
    media_path = Path(media_path)
    with open(media_path, "wb") as f:
        async for chunk in comm.stream():
            ctype = chunk["type"]
            if ctype == "audio":
                f.write(chunk["data"])
            elif ctype == "WordBoundary":
                start = chunk["offset"] / 1e7
                end = (chunk["offset"] + chunk["duration"]) / 1e7
                words.append({"w": chunk["text"], "start": round(start, 3),
                              "end": round(end, 3)})
    return words


def parse_word_srt(path: Path) -> list[dict]:
    """Parse an edge-tts word-boundary SRT into [{w,start,end}] (seconds). []
    if the file is missing or unparseable."""
    path = Path(path)
    if not path.exists():
        return []
    words: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    i = 0
    while i < len(lines):
        if "-->" in lines[i]:
            try:
                a, b = lines[i].split("-->")
                text = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if text:
                    words.append({"w": text, "start": _srt_ts(a), "end": _srt_ts(b)})
                i += 2
                continue
            except Exception:
                pass
        i += 1
    return words


def generate_scene_voiceover_edge_tts(text: str, voice: str, output_path: Path,
                                      rate: str = "+0%", pitch: str = "+0Hz") -> bool:
    """
    Generate voiceover for a single scene via the edge-tts Python API.

    Writes the MP3 to ``output_path`` and a **word-level** SRT alongside it
    (``.srt``) so downstream word-by-word text animation is synced to the
    narration. ``rate``/``pitch`` slow and deepen the voice (edge-tts prosody
    strings). Trims text if too long, same limit as the OpenAI backend.
    Returns True on success.
    """
    if len(text) > 300:
        text = text[:297] + "..."
    text = text.replace("—", "-").replace("“", '"').replace("”", '"')

    output_path = Path(output_path)
    try:
        words = asyncio.run(_edge_tts_synth(text, voice, output_path, rate, pitch))
    except Exception as e:
        print(f"  [edge-tts] Error: {e}")
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    if not output_path.exists() or output_path.stat().st_size == 0:
        print("  [edge-tts] Failed: no audio produced")
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    _write_word_srt(output_path.with_suffix(".srt"), words)
    size_kb = output_path.stat().st_size / 1024
    print(f"  [edge-tts] Saved {output_path.name} ({size_kb:.0f} KB, {len(words)} words)")
    return True


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

    # One consistent "wise grandfather" sage voice for every reel — with a
    # per-scene delivery arc (SCENE_PROSODY) instead of flat prosody.
    voice = REEL_VOICE
    print(f"  [edge-tts] Using sage voice '{voice}' (scene-arc prosody) "
          f"for mood '{mood}'")

    hook_path = out_dir / f"voice_hook_{timestamp}.mp3"
    quote_path = out_dir / f"voice_quote_{timestamp}.mp3"
    cta_path = out_dir / f"voice_cta_{timestamp}.mp3"

    hook_ok = generate_scene_voiceover_edge_tts(hook_text, voice, hook_path, *SCENE_PROSODY["hook"])
    quote_ok = generate_scene_voiceover_edge_tts(quote_text, voice, quote_path, *SCENE_PROSODY["quote"])
    cta_ok = generate_scene_voiceover_edge_tts(cta_text, voice, cta_path, *SCENE_PROSODY["cta"])

    return {
        "hook_voice": hook_path if hook_ok else None,
        "quote_voice": quote_path if quote_ok else None,
        "cta_voice": cta_path if cta_ok else None,
        "hook_words": parse_word_srt(hook_path.with_suffix(".srt")) if hook_ok else [],
        "quote_words": parse_word_srt(quote_path.with_suffix(".srt")) if quote_ok else [],
        "cta_words": parse_word_srt(cta_path.with_suffix(".srt")) if cta_ok else [],
        "voice": voice,
    }


def edge_tts_available() -> bool:
    """Check whether the edge-tts package is importable (no network, no PATH
    dependency — we use the Python API, not the CLI binary)."""
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False
