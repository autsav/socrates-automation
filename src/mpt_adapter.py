"""MPT output adapter: SRT → word_timings.json per spec schema.

MPT CLI always emits SRT (never JSON timings). This module translates
that SRT to the word_timings.json schema required by HyperFrames overlay
renderer and downstream consumers.
"""
import re
from typing import TypedDict


class WordTiming(TypedDict):
    t: float
    w: str


class SceneTiming(TypedDict):
    words: list[WordTiming]
    duration_sec: float
    start_sec: float


class WordTimingsOutput(TypedDict):
    scenes: dict[str, SceneTiming]
    total_duration_sec: float


_SRT_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def _parse_ts(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def srt_to_word_timings(srt_text: str) -> WordTimingsOutput:
    """Convert full SRT (one continuous timeline) → word_timings.json.

    MPT emits one SRT for the entire video. We populate all 4 scenes
    (hook/bridge/quote/cta) with start_sec=0 and the full word list.
    Downstream code (HF overlay orchestrator) slices by absolute time
    when rendering per-scene animations.

    Returns:
        {"scenes": {"hook": {"words": [...], "duration_sec": float, "start_sec": 0.0}, ...},
         "total_duration_sec": float}
    """
    blocks = re.split(r"\n\n+", srt_text.strip())
    words: list[WordTiming] = []
    last_end = 0.0
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        m = _SRT_TS_RE.match(lines[1])
        if not m:
            continue
        start_sec = _parse_ts(*m.groups()[:4])
        end_sec = _parse_ts(*m.groups()[4:])
        text = " ".join(lines[2:])
        for w in text.split():
            words.append({"t": round(start_sec, 3), "w": w})
        last_end = max(last_end, end_sec)

    scene_payload: SceneTiming = {
        "words": words,
        "duration_sec": round(last_end, 3),
        "start_sec": 0.0,
    }
    return {
        "scenes": {name: dict(scene_payload) for name in ("hook", "bridge", "quote", "cta")},
        "total_duration_sec": round(last_end, 3),
    }
