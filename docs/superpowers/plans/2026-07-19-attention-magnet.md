# Attention Magnet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild voice, footage, grade/pacing, and writing layers so reels read as "produced" — directed VO with a pre-quote silence drop, human-struggle footage cut on speech stress, film grade + punch-ins, a 7–15s `punch` arc, and a first-person mentor persona.

**Architecture:** Python side adds a voice-director (per-scene ElevenLabs settings + gravitas pitch-down + break tags), a dramatic multi-clip footage fetcher, and a `punch` story mode; the JSON bridge file grows a `backgrounds` list + `silenceDropSec`; Remotion adds `BackgroundReel` (stress-synced clip cuts) and `FilmGrade` (letterbox/grain) wrapping the existing composition. Every layer degrades to today's behavior on failure.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), pytest, ElevenLabs API, ffmpeg, Pexels API, Remotion 4 (TypeScript, `npx tsc --noEmit`).

## Global Constraints

- Never-crash contract: every new runtime stage is try/except best-effort; fallback = current behavior (spec: Error handling).
- Bridge-file back-compat: single-clip payloads stay byte-compatible — no `backgrounds` key unless ≥2 clips (spec 2).
- Pre-quote silence drop = 0.8s in the scene timeline, not baked into audio files (spec 1).
- Quote-VO gravitas pitch-down ≈ 5% via ffmpeg asetrate+atempo (spec 1).
- `punch` mode budgets: total spoken words 25–60, no reframe (spec 4); rotation share ~20% replacing one `classic` + one `question` slot in BOTH rotation tuples.
- Persona: first-person mentor POV + caption sign-off `— The Stoic Reset` (spec 5).
- DRAMATIC_POOLS entries: ≥6 per mood, all pass `trend_sources.is_unsafe`, all depict human motion/struggle (spec 2).
- `data/pipeline.db` never committed from local runs: `git checkout -- data/pipeline.db` before every commit.
- Tests: `.venv/bin/python -m pytest`; TS: `cd remotion && npx tsc --noEmit`. Files <500 lines.

## File Map

| File | Responsibility |
|---|---|
| `src/audio/voice_director.py` (new) | `delivery_profile(scene, chapter_index=None)`, `insert_chapter_breaks(text)`, `apply_gravitas(path)` |
| `src/visual/stock_footage.py` (mod) | `DRAMATIC_POOLS`, `_is_scenery(query)`, `fetch_reel_clips(mood, topic_query, n=4)` |
| `src/video/remotion_reel.py` (mod) | bridge file: `backgrounds` list + per-clip durations + `silenceDropSec`; SFX: riser + sub_impact |
| `pipeline.py` (mod) | wire voice profiles per scene; multi-clip fetch; `punch` arc in rotations + `_build_story_beats` punch mode |
| `studio/story_writer.py` (mod) | `punch` mode (validate_story mode param); persona in `_PREFIX` |
| `studio/copywriter.py` (mod) | persona + sign-off in draft prompt |
| `remotion/src/components/BackgroundReel.tsx` (new) | multi-clip background, cuts at given frames |
| `remotion/src/components/FilmGrade.tsx` (new) | letterbox + grain overlay |
| `remotion/src/PovReel.tsx` (mod) | wire BackgroundReel/FilmGrade, silence-drop offset for quote VO, speed-ramp into quote |
| `remotion/src/lib/cameraZoom.ts` (mod) | stronger punch-in kick (KICK 0.02→0.05) |

---

### Task 1: voice_director module

**Files:**
- Create: `src/audio/voice_director.py`
- Test: `tests/test_voice_director.py`

**Interfaces:**
- Consumes: nothing new (ffmpeg via subprocess; `elevenlabs_engine.DEFAULT_SETTINGS` shape: stability/similarity_boost/style/use_speaker_boost).
- Produces: `delivery_profile(scene: str, chapter_index: int | None = None) -> dict` (ElevenLabs voice_settings overrides); `insert_chapter_breaks(text: str) -> str` (adds `<break time="0.4s" />` between sentence groups of a bridge); `apply_gravitas(path: Path) -> bool` (in-place ~5% pitch-down; False on any failure). Task 4 wires these into pipeline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_voice_director.py
"""Directed delivery: per-scene ElevenLabs settings, chapter breaks, gravitas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio.voice_director import (
    delivery_profile, insert_chapter_breaks, apply_gravitas)


def test_profiles_differ_by_scene():
    hook = delivery_profile("hook")
    quote = delivery_profile("quote")
    cta = delivery_profile("cta")
    # Hook is expressive (low stability, high style); quote is gravitas
    # (high stability, low style). They must not be the same read.
    assert hook["stability"] < quote["stability"]
    assert hook["style"] > quote["style"]
    assert isinstance(cta, dict)


def test_bridge_urgency_builds_across_chapters():
    early = delivery_profile("bridge", chapter_index=0)
    late = delivery_profile("bridge", chapter_index=4)
    assert late["stability"] < early["stability"]  # urgency rises


def test_unknown_scene_returns_empty_overrides():
    assert delivery_profile("nonsense") == {}


def test_chapter_breaks_inserted_between_sentence_groups():
    text = ("He walked into the storm. No shoes. His friends stared. "
            "He smiled back. Then he did it again the next day. Nobody laughed then.")
    out = insert_chapter_breaks(text)
    assert '<break time="0.4s" />' in out
    # Original words all survive.
    for w in ("storm", "friends", "smiled", "Nobody"):
        assert w in out


def test_apply_gravitas_returns_false_on_missing_file(tmp_path):
    assert apply_gravitas(tmp_path / "nope.mp3") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_voice_director.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'src.audio.voice_director'`

- [ ] **Step 3: Implement**

```python
# src/audio/voice_director.py
"""Per-scene delivery direction for ElevenLabs narration (spec 1).
One flat read is the tell of TTS; profiles give each scene a performance:
hook attacks, the story builds urgency, the quote lands slow and low."""
import re
import shutil
import subprocess
from pathlib import Path

# Overrides merged over elevenlabs_engine.DEFAULT_SETTINGS by the caller.
_PROFILES = {
    "hook":  {"stability": 0.22, "style": 0.55},   # intense, fast attack
    "quote": {"stability": 0.70, "style": 0.05},   # slow gravitas
    "cta":   {"stability": 0.40, "style": 0.30},   # direct, close
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
    gap — peer-reviewed finding). In-place; best-effort; False on failure."""
    try:
        path = Path(path)
        if not path.exists() or not shutil.which("ffmpeg"):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_voice_director.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/audio/voice_director.py tests/test_voice_director.py
git commit -m "feat(voice): per-scene delivery profiles, chapter breaks, gravitas pitch-down (spec 1)"
```

### Task 2: dramatic footage engine

**Files:**
- Modify: `src/visual/stock_footage.py`
- Test: `tests/test_dramatic_footage.py`

**Interfaces:**
- Consumes: existing `search_stock_video(mood, api_key, query=None)`, `pick_best_video`, `download_stock_video`, `fetch_stock_background(mood, api_key, output_dir, query=None)`.
- Produces: `DRAMATIC_POOLS: dict[str, list[str]]` (same mood keys as `MOOD_SEARCH_TERMS`); `_is_scenery(query: str) -> bool`; `fetch_reel_clips(mood, api_key, output_dir, topic_query=None, n=4) -> list[Path]` (deduped by video id; ≥1 clip on success; [] on total failure — caller falls back to `fetch_stock_background`). Task 4 consumes `fetch_reel_clips`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dramatic_footage.py
"""Dramatic pools: human struggle, not scenery — the emotional charge the
winning accounts borrow from movie clips (spec 2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual import stock_footage as sf
from src.content.trend_sources import is_unsafe


def test_pools_cover_all_moods_with_six_plus_safe_queries():
    for mood in sf.MOOD_SEARCH_TERMS:
        pool = sf.DRAMATIC_POOLS[mood]
        assert len(pool) >= 6, mood
        for q in pool:
            assert not is_unsafe(q), q
            assert not sf._is_scenery(q), q


def test_scenery_heuristic():
    assert sf._is_scenery("beautiful sunset over ocean")
    assert sf._is_scenery("mountain landscape clouds")
    assert not sf._is_scenery("boxer wrapping hands dark gym")
    assert not sf._is_scenery("man walking into storm rain")


def test_fetch_reel_clips_dedupes_and_survives_failures(tmp_path, monkeypatch):
    calls = []

    def fake_search(mood, api_key, query=None):
        calls.append(query)
        return [{"id": 1, "video_files": []}] if len(calls) < 3 else [{"id": 2, "video_files": []}]

    monkeypatch.setattr(sf, "search_stock_video", fake_search)
    monkeypatch.setattr(sf, "pick_best_video", lambda v, **k: v[0])

    def fake_download(video, output_path):
        p = Path(output_path)
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(sf, "download_stock_video", fake_download)
    clips = sf.fetch_reel_clips("dark_philosophical", "key", tmp_path, n=4)
    assert 1 <= len(clips) <= 2          # id 1 deduped, id 2 distinct
    assert all(p.exists() for p in clips)


def test_fetch_reel_clips_total_failure_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "search_stock_video",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("api down")))
    assert sf.fetch_reel_clips("dark_philosophical", "key", tmp_path) == []
```

- [ ] **Step 2: Run** — FAIL `AttributeError: DRAMATIC_POOLS`.

- [ ] **Step 3: Implement** — add to `src/visual/stock_footage.py`:

```python
# Human-struggle queries per mood (spec 2): motion + conflict + a person.
# Winning accounts borrow emotional charge from movie/anime clips; a licensed
# pipeline borrows it from footage of humans STRUGGLING, never scenery.
DRAMATIC_POOLS = {
    "calm_stoic": [
        "man meditating dark room candle", "swimmer cold water winter lake",
        "monk walking temple rain", "man breathing heavy eyes closed",
        "hands in prayer dark", "man sitting alone empty gym"],
    "cinematic_hopeful": [
        "runner sunrise city street", "climber reaching summit exhausted",
        "man opening curtains morning light", "athlete training dawn stairs",
        "woman running uphill determined", "boxer victory arms raised"],
    "dark_philosophical": [
        "man walking into storm rain", "boxer wrapping hands dark gym",
        "silhouette training night city", "man staring window rain night",
        "hands gripping rope struggle", "runner collapsing exhausted track"],
    "dramatic_ancient": [
        "blacksmith forging fire sparks", "man carrying heavy stone",
        "warrior training sword silhouette", "hands working clay pottery",
        "man rowing boat storm", "torch flame dark corridor"],
    "epic_warrior": [
        "boxer heavy bag slow motion", "sprinter starting blocks explosive",
        "man flipping tire gym", "wrestler training takedown",
        "martial artist kick training", "athlete screaming effort barbell"],
    "mystical_greek": [
        "man walking ancient ruins alone", "hand touching marble statue",
        "figure in fog walking", "candle flame dark library",
        "man reading old book candlelight", "silhouette columns moonlight"],
    "stark_minimal": [
        "man alone empty room window", "single figure crossing bridge fog",
        "hands clenched fist close up", "man staring mirror intense",
        "footsteps empty corridor", "man standing rooftop city night"],
}

_SCENERY_WORDS = {
    "sunset", "sunrise", "ocean", "beach", "landscape", "mountain", "clouds",
    "sky", "forest", "waterfall", "flowers", "nature", "scenery", "aerial",
    "drone", "lake", "waves",
}
_HUMAN_WORDS = {
    "man", "woman", "boxer", "runner", "athlete", "climber", "swimmer",
    "warrior", "monk", "hands", "figure", "silhouette", "person", "wrestler",
    "sprinter", "blacksmith", "martial",
}


def _is_scenery(query: str) -> bool:
    """True when a query is passive scenery with no human in frame — the
    look of every low-effort quote account (spec 2)."""
    words = set((query or "").lower().split())
    return bool(words & _SCENERY_WORDS) and not (words & _HUMAN_WORDS)


def fetch_reel_clips(mood, api_key, output_dir, topic_query=None, n=4):
    """Up to n distinct dramatic clips: topic_query first (when it depicts a
    human), then dramatic-pool picks. Deduped by Pexels video id. Returns []
    on total failure — callers fall back to the single-clip path."""
    queries = []
    if topic_query and not _is_scenery(topic_query):
        queries.append(topic_query)
    queries += DRAMATIC_POOLS.get(mood, DRAMATIC_POOLS["dark_philosophical"])
    clips, seen_ids = [], set()
    for i, q in enumerate(queries):
        if len(clips) >= n:
            break
        try:
            videos = search_stock_video(mood, api_key, query=q)
            video = pick_best_video(videos) if videos else None
            if not video or video.get("id") in seen_ids:
                continue
            seen_ids.add(video.get("id"))
            dest = Path(output_dir) / f"reel_clip_{len(clips)}_{video.get('id')}.mp4"
            got = download_stock_video(video, dest)
            if got:
                clips.append(Path(got))
        except Exception as e:  # noqa: BLE001 - one dead query never stops the fetch
            print(f"  [stock] clip query failed ({e}) — continuing")
    return clips
```

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest tests/test_dramatic_footage.py -q` → `4 passed`; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/visual/stock_footage.py tests/test_dramatic_footage.py
git commit -m "feat(visual): dramatic human-struggle pools + multi-clip fetch (spec 2)"
```

### Task 3: punch arc + persona (Python writing layer)

**Files:**
- Modify: `studio/story_writer.py` (punch mode + persona in `_PREFIX`), `studio/copywriter.py` (persona + sign-off), `pipeline.py` (rotations + `_build_story_beats` punch mode + `_apply_arc` passthrough)
- Test: `tests/test_punch_arc.py`

**Interfaces:**
- Consumes: `validate_story(d, min_total=...)` (existing), `_ARC_ROTATION_TREND/_NO_TREND` tuples in pipeline.py, `pick_debate`/`pick_weird` material pickers.
- Produces: `validate_story(d, min_total=MIN_SPOKEN_WORDS, mode="story")` — `mode="punch"`: total 25–60 words, empty reframe ALLOWED (skip reframe checks); `write_story(client, mode, ...)` accepts mode `"punch"` (prompt says: one brutal line ≤10 words as hook, NO reframe — set beat_reframe to "", CTA is a send line); pipeline rotations updated: TREND `("story", "story", "weird", "punch", "question", "story", "cold_open", "weird", "story", "punch")`, NO_TREND `("weird", "punch", "story", "question", "weird", "cold_open", "story", "punch", "weird", "question")`; `_run_pov_reel` treats `punch` like story/weird for generation (mode="punch", material = debate topic) but with NO bridge scene; caption sign-off appended: `\n— The Stoic Reset`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_punch_arc.py
"""7-15s punch arc: one brutal line -> quote -> send CTA (spec 4) + persona."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from studio.story_writer import validate_story, _PREFIX


def test_punch_mode_budgets():
    good = {"beat_hook": "Nobody is coming to save you.",
            "beat_reframe": "",
            "quote_row": 3, "beat_cta": "Send this to the friend still waiting.",
            "topic_query": "man alone rooftop", "caption_first_line": "Read that again."}
    ok, r = validate_story(good, mode="punch")
    assert ok, r
    # Story mode still enforces the long-form floor.
    assert validate_story(good)[0] is False
    too_long = dict(good, beat_hook=" ".join(["word"] * 40),
                    beat_cta=" ".join(["word"] * 40))
    assert validate_story(too_long, mode="punch")[0] is False


def test_rotations_contain_punch_at_twenty_percent():
    for rot in (pipeline._ARC_ROTATION_TREND, pipeline._ARC_ROTATION_NO_TREND):
        assert rot.count("punch") == 2 and len(rot) == 10


def test_persona_in_prefix():
    assert "first person" in _PREFIX.lower() or '"I"' in _PREFIX


def test_signoff_appended_to_caption():
    cap = pipeline._append_signoff("Line one.\n#stoic")
    assert cap.rstrip().endswith("— The Stoic Reset") is False  # hashtags last
    assert "— The Stoic Reset" in cap
    # Idempotent: never doubled.
    assert pipeline._append_signoff(cap).count("— The Stoic Reset") == 1
```

- [ ] **Step 2: Run** — FAIL (`validate_story() got an unexpected keyword argument 'mode'`).

- [ ] **Step 3: Implement**

In `studio/story_writer.py`:

```python
PUNCH_MIN, PUNCH_MAX = 25, 60


def validate_story(d: dict, min_total: int = MIN_SPOKEN_WORDS,
                   mode: str = "story") -> tuple[bool, str]:
    try:
        hook = (d.get("beat_hook") or "").strip()
        reframe = (d.get("beat_reframe") or "").strip()
        cta = (d.get("beat_cta") or "").strip()
        if not hook or not cta:
            return False, "empty beat"
        if mode != "punch" and not reframe:
            return False, "empty beat"
        if len(hook.split()) > 15:
            return False, f"hook too long ({len(hook.split())} words)"
        if hook.rstrip().endswith("?"):
            return False, "hook must be a statement, not a question"
        total = len(hook.split()) + len(reframe.split()) + len(cta.split())
        if mode == "punch":
            if not (PUNCH_MIN <= total <= PUNCH_MAX):
                return False, f"punch total {total} outside {PUNCH_MIN}-{PUNCH_MAX}"
        else:
            if len(reframe.split()) > 185:
                return False, f"reframe too long ({len(reframe.split())} words)"
            if total < min_total:
                return False, f"total spoken words {total} < {min_total} (needs a ~60s story)"
            if total > MAX_SPOKEN_WORDS:
                return False, f"total spoken words {total} > {MAX_SPOKEN_WORDS}"
        if not isinstance(d.get("quote_row"), int):
            return False, "quote_row must be an integer"
        return True, "ok"
    except (TypeError, AttributeError) as e:
        return False, f"malformed: {e}"
```

`write_story`: pass `mode` through to both `validate_story` calls (`validate_story(d or {}, mode=mode)`); in `_ROLE_DEFAULT` add one line to the beat instructions: `"For punch mode: beat_hook is ONE brutal line (<=10 words), beat_reframe MUST be an empty string, total spoken words 25-60 — a 7-15 second reel.\n"`. In `_PREFIX` append: `" Write in first person — a mentor speaking directly to one reader as \"I\" and \"you\"."`

In `studio/copywriter.py` `_DRAFT_ROLE_DEFAULT` append: `"\nWrite captions in first person — a mentor speaking to one reader.\n"`.

In `pipeline.py`:

```python
_ARC_ROTATION_TREND = ("story", "story", "weird", "punch", "question", "story", "cold_open", "weird", "story", "punch")
_ARC_ROTATION_NO_TREND = ("weird", "punch", "story", "question", "weird", "cold_open", "story", "punch", "weird", "question")

_SIGNOFF = "— The Stoic Reset"


def _append_signoff(caption: str) -> str:
    """Persona sign-off (spec 5) above the hashtag block; idempotent."""
    if _SIGNOFF in (caption or ""):
        return caption
    lines = (caption or "").split("\n")
    tag_start = next((i for i, l in enumerate(lines) if l.strip().startswith("#")),
                     len(lines))
    return "\n".join(lines[:tag_start] + [_SIGNOFF] + lines[tag_start:])
```

`_build_story_beats`: `punch` arc → `material, mode = pick_debate(row), "punch"` (add `arc == "punch"` branch before the trend branch). `_run_pov_reel`: include `"punch"` in the `arc in ("story", "weird")` checks (story generation AND the `_bridge_for_vo` bypass — but for punch the story's `beat_reframe` is empty so no bridge scene renders, which is the format). Apply `_append_signoff` to the caption in the caption-levers block.

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest tests/test_punch_arc.py tests/test_content_brains.py tests/test_viral_arcs.py tests/test_reel_arcs.py -q` → all pass (rotation-distribution tests in test_viral_arcs.py assert old tuples — update their expected counts to the new tuples); full suite green.

- [ ] **Step 5: Commit**

```bash
git add studio/story_writer.py studio/copywriter.py pipeline.py tests/test_punch_arc.py tests/test_viral_arcs.py
git commit -m "feat(arcs): 7-15s punch arc + first-person mentor persona + caption sign-off (spec 4+5)"
```

### Task 4: pipeline wiring — directed VO + multi-clip + silence drop payload

**Files:**
- Modify: `pipeline.py` (VO block: per-scene settings, chapter breaks, gravitas; footage block: fetch_reel_clips), `src/video/remotion_reel.py` (bridge payload: `backgrounds` list + `backgroundDurationsSec` + `silenceDropSec`; SFX riser + sub_impact)
- Test: `tests/test_cinematic_wiring.py`

**Interfaces:**
- Consumes: `voice_director.delivery_profile/insert_chapter_breaks/apply_gravitas` (Task 1); `stock_footage.fetch_reel_clips` (Task 2).
- Produces: `write_bridge_file(..., backgrounds: list[Path] | None = None, silence_drop_sec: float = 0.0)` — with ≥2 clips writes `payload["backgrounds"] = [names]` + `payload["backgroundDurationsSec"] = [floats]` and does NOT write the legacy `background` key; with 0–1 clips the legacy single-`background` payload is byte-identical to today. `payload["silenceDropSec"]` written only when > 0. `_synth_sfx` additionally produces `riser` (1.2s pink-noise swell, afade in) and `sub_impact` (0.5s 55Hz sine with fast decay) entries. Task 5's Remotion props consume `backgrounds`/`backgroundDurationsSec`/`silenceDropSec`/`sfx.riser`/`sfx.sub_impact`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cinematic_wiring.py
"""Bridge-file payload: multi-clip backgrounds + silence drop, back-compatible."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.remotion_reel import write_bridge_file


def _write(tmp_path, **kw):
    p = tmp_path / "reel-data.json"
    write_bridge_file(hook="h", quote="q", attribution="— S", cta="c",
                      mood="dark_philosophical", duration=10, fps=30,
                      bridge_path=p, **kw)
    return json.loads(p.read_text())


def test_single_clip_payload_unchanged(tmp_path):
    clip = tmp_path / "one.mp4"; clip.write_bytes(b"x")
    d = _write(tmp_path, background=clip)
    assert "backgrounds" not in d and d["background"] == "bg.mp4"
    assert "silenceDropSec" not in d


def test_multi_clip_payload(tmp_path):
    clips = []
    for i in range(3):
        c = tmp_path / f"c{i}.mp4"; c.write_bytes(b"x"); clips.append(c)
    d = _write(tmp_path, backgrounds=clips, silence_drop_sec=0.8)
    assert len(d["backgrounds"]) == 3
    assert "background" not in d
    assert len(d["backgroundDurationsSec"]) == 3
    assert d["silenceDropSec"] == 0.8


def test_sfx_set_includes_riser_and_sub_impact(tmp_path):
    d = _write(tmp_path)
    if d.get("sfx"):                      # ffmpeg present in env
        assert "riser" in d["sfx"] and "sub_impact" in d["sfx"]
```

- [ ] **Step 2: Run** — FAIL (`unexpected keyword argument 'backgrounds'`).

- [ ] **Step 3: Implement**

`src/video/remotion_reel.py` — `write_bridge_file` gains `backgrounds: list | None = None, silence_drop_sec: float = 0.0`. After the existing single-`background` handling:

```python
    bg_names, bg_durs = [], []
    if backgrounds and len([b for b in backgrounds if b and Path(b).exists()]) >= 2:
        for i, b in enumerate(backgrounds):
            b = Path(b)
            if not b.exists():
                continue
            nm = _copy_audio(b, f"bg{i}{b.suffix}")
            if nm:
                bg_names.append(nm)
                bg_durs.append(_probe_duration(b) or 0.0)
```

and in the payload section:

```python
    if bg_names:
        payload["backgrounds"] = bg_names
        payload["backgroundDurationsSec"] = bg_durs
        payload.pop("background", None)
        payload.pop("backgroundDurationSec", None)
    if silence_drop_sec > 0:
        payload["silenceDropSec"] = round(float(silence_drop_sec), 3)
```

`_synth_sfx` — add after the impact block (same style, best-effort):

```python
    riser = dest_dir / "sfx-riser.wav"
    sub = dest_dir / "sfx-sub.wav"
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=d=1.2:c=pink:a=0.30",
             "-af", "lowpass=f=900,afade=t=in:d=1.05,afade=t=out:st=1.05:d=0.15",
             "-ac", "1", str(riser)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and riser.exists():
            result["riser"] = riser.name
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=55:duration=0.5",
             "-af", "afade=t=out:st=0.08:d=0.42,volume=1.6", "-ac", "1", str(sub)],
            capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and sub.exists():
            result["sub_impact"] = sub.name
    except Exception:
        pass
```

`generate_remotion_reel` passes `backgrounds`/`silence_drop_sec` through to `write_bridge_file` (add both params, default None/0.0).

`pipeline.py` `_run_pov_reel`:
- Footage block: try `clips = fetch_reel_clips(mood, cfg.PEXELS_API_KEY, OUTPUT_DIR, topic_query=quote_data.get("topic_query") or None)`; if `len(clips) >= 2` pass `backgrounds=clips` (and set `background=None`), elif 1 clip use it as the single `background`, else existing `fetch_stock_background` fallback. Whole block try/except → existing path.
- VO block: for each scene call, merge `delivery_profile(scene)` into the settings argument (`_el_scene(text, voice, path, key, settings=delivery_profile("hook"))` — verify `generate_scene_voiceover` accepts `settings` and pass through). Bridge text goes through `insert_chapter_breaks` BEFORE VO generation (breaks affect narration only, not the on-screen `bridge` text — pass the un-tagged text in the payload). After quote VO succeeds: `apply_gravitas(quote_voice_path)` best-effort. Set `silence_drop_sec=0.8` when a quote VO exists.
- All wiring try/except; on any failure the old single-read path runs.

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest tests/test_cinematic_wiring.py tests/test_remotion_reel.py -q` → pass (update any bridge-payload-shape tests that enumerate keys); full suite green.

- [ ] **Step 5: Commit**

```bash
git add pipeline.py src/video/remotion_reel.py tests/test_cinematic_wiring.py
git commit -m "feat(pipeline): directed VO wiring, multi-clip payload, silence drop, riser+sub SFX (spec 1+2)"
```

### Task 5: Remotion — BackgroundReel, FilmGrade, silence drop, speed ramp

**Files:**
- Create: `remotion/src/components/BackgroundReel.tsx`, `remotion/src/components/FilmGrade.tsx`
- Modify: `remotion/src/PovReel.tsx`, `remotion/src/lib/cameraZoom.ts` (KICK 0.02 → 0.05)
- Test: `cd remotion && npx tsc --noEmit` (no JS test framework in repo; frame verification happens in Task 6)

**Interfaces:**
- Consumes: `PovReelProps` gains `backgrounds?: string[]`, `backgroundDurationsSec?: number[]`, `silenceDropSec?: number`, `sfx` gains `riser?: string; sub_impact?: string` — matching Task 4's payload keys exactly.
- Produces: BackgroundReel renders clip i for scene-segment i (cut frames derived below); FilmGrade wraps the whole composition.

- [ ] **Step 1: BackgroundReel.tsx**

```tsx
import React from "react";
import { AbsoluteFill, Sequence, useVideoConfig } from "remotion";
import { BackgroundPhoto } from "./BackgroundPhoto";

/** Multi-clip background: each clip owns a span of the reel, cutting on the
 *  given frame boundaries (scene starts + mid-bridge stress points). One clip
 *  → identical to BackgroundPhoto. */
export const BackgroundReel: React.FC<{
  clips: string[];
  clipDurationsSec: number[];
  cutFrames: number[]; // ascending, first must be 0
}> = ({ clips, clipDurationsSec, cutFrames }) => {
  const { durationInFrames } = useVideoConfig();
  if (clips.length === 0) return null;
  if (clips.length === 1) {
    return <BackgroundPhoto src={clips[0]} videoDurationSec={clipDurationsSec[0]} />;
  }
  const starts = cutFrames.length ? cutFrames : [0];
  return (
    <AbsoluteFill>
      {clips.map((clip, i) => {
        const from = starts[Math.min(i, starts.length - 1)];
        const to = i + 1 < starts.length ? starts[i + 1] : durationInFrames;
        if (to <= from) return null;
        return (
          <Sequence key={clip} from={from} durationInFrames={to - from} name={`BG${i}`}>
            <BackgroundPhoto src={clip} videoDurationSec={clipDurationsSec[i]} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: FilmGrade.tsx**

```tsx
import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

/** Cinematic pass: letterbox bars + animated grain. Sits above the background,
 *  below text. Pure visuals — no runtime failure path. */
export const FilmGrade: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const barPct = 8;
  // Grain: jitter an SVG-noise tile's offset per frame.
  const gx = (frame * 37) % 100;
  const gy = (frame * 53) % 100;
  return (
    <AbsoluteFill>
      {children}
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          opacity: 0.07,
          backgroundImage:
            `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
          backgroundPosition: `${gx}px ${gy}px`,
        }}
      />
      <div style={{ position: "absolute", top: 0, left: 0, right: 0,
                    height: `${barPct}%`, background: "black" }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0,
                    height: `${barPct}%`, background: "black" }} />
    </AbsoluteFill>
  );
};
```

- [ ] **Step 3: Wire PovReel.tsx**

- Props: add `backgrounds?: string[]; backgroundDurationsSec?: number[]; silenceDropSec?: number;` and extend `sfx` type with `riser?: string; sub_impact?: string;` (+ defaults in `povReelDefaultProps`).
- Cut frames: scene starts (`0, hookF, quoteStart, quoteEnd`) plus, when a bridge exists and `wordTimes.bridge` present, mid-bridge stress cuts every ~4s: take `wordTimes.bridge` entries at 7-word chunk starts (`hookF + Math.round(wt[i*7].start * fps)`) keeping only points ≥3s after the previous cut; total cut list clamped to `backgrounds.length` segments.
- Background render: `backgrounds && backgrounds.length >= 2 ? <BackgroundReel clips={backgrounds} clipDurationsSec={backgroundDurationsSec ?? []} cutFrames={cuts} /> : (existing single-background / gradient branch)`.
- Wrap the ColorGrade content in `<FilmGrade>` (inside ColorGrade so the grade applies to bars-free area; bars over graded video).
- **Silence drop:** when `silenceDropSec` > 0, QuoteVO's `<Sequence from={quoteStart + Math.round(silenceDropSec * fps)}>` (audio starts late; the visual quote scene still starts at quoteStart) and music volume forced to 0.02 during `[quoteStart, quoteStart + drop]` via the duckVolume spans. Riser plays `<Sequence from={quoteStart - 36} durationInFrames={36}>` at volume 0.3 when `sfx.riser`; sub_impact at the first quote beat frame at volume 0.4 when `sfx.sub_impact`.
- **Speed ramp:** in `cameraZoom.ts`, KICK 0.02 → 0.05; add to PovReel a scale ease `interpolate(frame, [quoteStart - 12, quoteStart], [1, 1.08])` multiplied into the existing `scale` for that window (clamped both sides).

- [ ] **Step 4: Type-check** — `cd remotion && npx tsc --noEmit` → clean.

- [ ] **Step 5: Commit**

```bash
git add remotion/src/components/BackgroundReel.tsx remotion/src/components/FilmGrade.tsx remotion/src/PovReel.tsx remotion/src/lib/cameraZoom.ts
git commit -m "feat(remotion): multi-clip cuts, film grade, silence drop, speed ramp (spec 3)"
```

### Task 6: Verification gate

- [ ] Full suite: `.venv/bin/python -m pytest -q` → green (expect ~700+).
- [ ] `cd remotion && npx tsc --noEmit` → clean.
- [ ] Dry-run STORY reel: `echo '{"row_number": 42}' > /tmp/seed.json && .venv/bin/python pipeline.py --remotion --dry-run --content /tmp/seed.json` (detached; render can exceed 10 min). Verify from the output MP4: ffprobe duration ≥60s; extract frames at 1s/10s/25s — letterbox bars + grain visible, DIFFERENT background clips across frames (multi-clip cuts), hook text at frame 0; audio: audible gap then low-pitch quote (silence drop + gravitas).
- [ ] Dry-run PUNCH reel: seed a row where the rotation yields `punch` (with-trend rows ≡3 or 9 mod 10; no-trend rows ≡1 or 7 mod 10 — e.g. `{"row_number": 43}` w/ trend). Verify duration 7–20s, no bridge scene.
- [ ] `git checkout -- data/pipeline.db`; `git pull --rebase --autostash && git push`.
- [ ] Live acceptance at next open slot: one post; Graph read-back (permalink + first comment); confirm caption carries `— The Stoic Reset`.

## Self-Review (done)

- Spec coverage: 1→T1+T4(+T5 riser/sub/silence), 2→T2+T4, 3→T5, 4→T3, 5→T3, error handling→every task's fallbacks, testing→each task + T6. No gaps.
- Placeholders: none. T5 has prose-described wiring with exact prop names, frames, and volumes; component code complete.
- Type consistency: `fetch_reel_clips(mood, api_key, output_dir, topic_query=None, n=4)` (T2) = T4 call; payload keys `backgrounds`/`backgroundDurationsSec`/`silenceDropSec`/`sfx.riser`/`sfx.sub_impact` (T4) = T5 props; `validate_story(d, min_total, mode)` (T3) matches its callers; `delivery_profile/insert_chapter_breaks/apply_gravitas` (T1) = T4 usage.
