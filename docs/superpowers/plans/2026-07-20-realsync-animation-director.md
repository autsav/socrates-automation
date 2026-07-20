# Real-Sync + Animation Director Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace faked even-spread ElevenLabs word timings with real API timestamps, then drive a deterministic per-word animation technique pack (cinematic-kinetic) off the true timings.

**Architecture:** Python gets real character alignment from ElevenLabs' with-timestamps endpoint → word-level SRT; a pure classifier tags each payload word with a class (`num/neg/power/stress/end/plain`); Remotion's new `animDirector.effectFor` maps class+seed → one of 5 word effects applied inside the existing text components. Everything is additive — payloads without `cls` render exactly as today.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), pytest, ElevenLabs REST, Remotion 4 TypeScript (`npx tsc --noEmit`).

## Global Constraints

- Style boundary: cinematic-kinetic only — NO emoji/meme effects (spec: Locked decisions).
- Determinism: per-row `animSeed`; same inputs → same render.
- Back-compat: payloads without `cls`/`animSeed` render exactly as today; with-timestamps failure → plain endpoint + estimated timings (one retry, one log line).
- cls priority when multiple match: `num > neg > power > end > stress > plain`, single cls per word (spec 2).
- countup only for ints ≤ 9999, else falls back to pop (spec 3/5).
- `data/pipeline.db` is NOT tracked — never `git add` it (or `-f`); it may be dirty from concurrent runs, leave it alone.
- Tests: `.venv/bin/python -m pytest`; TS: `cd remotion && npx tsc --noEmit`. Files <500 lines.

## File Map

| File | Responsibility |
|---|---|
| `src/audio/elevenlabs_engine.py` (mod) | with-timestamps call, `_alignment_to_words`, real-SRT writing w/ estimation fallback |
| `src/video/word_classes.py` (new) | `classify_words(words) -> words+cls` pure classifier |
| `src/video/remotion_reel.py` (mod) | `write_bridge_file` runs classify_words on all wordTimes; `anim_seed` param → `payload["animSeed"]` |
| `pipeline.py` (mod) | passes `anim_seed=row_number or 0` |
| `remotion/src/lib/wordAt.ts` (mod) | `WordTime.cls?: string` |
| `remotion/src/lib/animDirector.ts` (new) | `effectFor(cls, index, seed) -> WordFx` |
| `remotion/src/components/AnimatedText.tsx` (mod) | apply pop/shake/glowpop/countup per word |
| `remotion/src/components/AnimatedQuote.tsx` (mod) | letter-cascade from real word spans |
| `remotion/src/components/BridgeScene.tsx` (mod) | sentence-end white tick on chunk cuts |
| `remotion/src/components/CtaScene.tsx` (mod) | freeze-pop at CTA VO end |
| `remotion/src/PovReel.tsx` (mod) | ghost-trail in speed-ramp window; animSeed prop plumbing |

---

### Task 1: Real timestamps from ElevenLabs

**Files:**
- Modify: `src/audio/elevenlabs_engine.py`
- Test: `tests/test_real_timestamps.py`

**Interfaces:**
- Consumes: existing `generate_voiceover(text, api_key, voice, output_path, settings)` and `generate_scene_voiceover(text, voice, output_path, api_key, settings)` (writes `.srt` next to the mp3 from `_estimate_word_timings` today; SRT entries parsed elsewhere by `edge_tts_engine.parse_word_srt` into `{"w","start","end"}`).
- Produces: `_alignment_to_words(text: str, alignment: dict) -> list[dict]` (`[{"w","start","end"}]`, `[]` on malformed); `generate_voiceover` returns `(path, words)` INTERNALLY via a new private `_generate_with_timestamps(...) -> tuple[Path|None, list[dict]]` while the PUBLIC `generate_voiceover` signature stays `-> Path|None` (callers unbroken); `generate_scene_voiceover` uses the real words for the SRT when non-empty, else estimation.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_real_timestamps.py
"""Real word timings from ElevenLabs character alignment (spec 1).
The faked even-spread timings were the voice/text desync root cause."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio.elevenlabs_engine import _alignment_to_words


def _align(chars, starts, ends):
    return {"characters": chars, "character_start_times_seconds": starts,
            "character_end_times_seconds": ends}


def test_groups_characters_into_words():
    text = "He walked."
    chars = list("He walked.")
    starts = [0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]
    ends = [s + 0.05 for s in starts]
    words = _alignment_to_words(text, _align(chars, starts, ends))
    assert [w["w"] for w in words] == ["He", "walked."]
    assert words[0]["start"] == 0.0 and words[0]["end"] == 0.15
    assert words[1]["start"] == 0.3          # 'w' starts after the space
    assert words[1]["end"] == 0.65


def test_break_tags_excluded():
    text = 'One. <break time="0.4s" /> Two.'
    chars = list(text)
    starts = [round(i * 0.05, 2) for i in range(len(chars))]
    ends = [s + 0.04 for s in starts]
    words = _alignment_to_words(text, _align(chars, starts, ends))
    assert [w["w"] for w in words] == ["One.", "Two."]


def test_malformed_alignment_returns_empty():
    assert _alignment_to_words("hi", None) == []
    assert _alignment_to_words("hi", {}) == []
    assert _alignment_to_words("hi", {"characters": ["h"],
                                      "character_start_times_seconds": []}) == []
```

- [ ] **Step 2: Run** — `.venv/bin/python -m pytest tests/test_real_timestamps.py -q` → FAIL `ImportError: cannot import name '_alignment_to_words'`.

- [ ] **Step 3: Implement** in `src/audio/elevenlabs_engine.py`:

```python
import base64
import re

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
```

In `generate_voiceover`, replace the plain request with a with-timestamps attempt + fallback. Split the POST into a helper so both paths share headers/body:

```python
    body = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
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
        print(f"  [elevenlabs] with-timestamps unavailable ({e}) — plain endpoint")
        response = requests.post(
            f"{ELEVENLABS_API}/text-to-speech/{voice_id}",
            headers={**headers, "Accept": "audio/mpeg"}, json=body, timeout=30)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
```

Store the words on a module-side channel the scene wrapper can read without changing the public signature: set `generate_voiceover.last_words = words` right before returning the path (and `= []` on the fallback path). In `generate_scene_voiceover`, after `generate_voiceover` succeeds:

```python
    real = getattr(generate_voiceover, "last_words", []) or []
    duration = _get_audio_duration(result)
    words = real if real else _estimate_word_timings(text, duration)
```

(Keep the existing SRT writing loop unchanged — it consumes the same `[{"w","start","end"}]` shape; adjust the loop's key names if they differ.)

- [ ] **Step 4: Run** — targeted tests pass; full suite green (existing elevenlabs tests may mock `requests.post` once — the with-timestamps attempt changes call count/URL; update those mocks minimally to answer the new URL).

- [ ] **Step 5: Commit**

```bash
git add src/audio/elevenlabs_engine.py tests/test_real_timestamps.py
git commit -m "feat(sync): real ElevenLabs word timestamps via with-timestamps endpoint (spec 1)"
```

### Task 2: Word classifier

**Files:**
- Create: `src/video/word_classes.py`
- Test: `tests/test_word_classes.py`

**Interfaces:**
- Consumes: word dicts `{"w","start","end"}`.
- Produces: `classify_words(words: list[dict]) -> list[dict]` — same objects + `cls` key; priority `num > neg > power > end > stress > plain`; never raises. Task 3 calls it in write_bridge_file.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_word_classes.py
"""Per-word animation classes (spec 2) — pure, prioritized, never raises."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.word_classes import classify_words


def _words(text):
    return [{"w": w, "start": i * 0.3, "end": i * 0.3 + 0.25}
            for i, w in enumerate(text.split())]


def test_classes_assigned():
    out = classify_words(_words("He owned 300 ships. Nobody understood him."))
    by_word = {w["w"]: w["cls"] for w in out}
    assert by_word["300"] == "num"
    assert by_word["Nobody"] == "neg"
    assert by_word["ships."] == "end"          # sentence-terminal
    assert by_word["understood"] in ("stress", "plain")
    assert by_word["him."] == "end"


def test_priority_num_beats_end():
    out = classify_words(_words("He lost 40."))
    assert {w["w"]: w["cls"] for w in out}["40."] == "num"


def test_power_words_tagged():
    out = classify_words(_words("The fear was real"))
    assert {w["w"]: w["cls"] for w in out}["fear"] == "power"


def test_stress_is_longest_word_per_sentence():
    out = classify_words(_words("He rehearsed poverty monthly"))
    assert {w["w"]: w["cls"] for w in out}["rehearsed"] == "stress"


def test_garbage_never_raises():
    assert classify_words([]) == []
    out = classify_words([{"w": None, "start": 0, "end": 1}])
    assert out[0]["cls"] == "plain"
```

- [ ] **Step 2: Run** — FAIL ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/video/word_classes.py
"""Per-word animation classes for the Remotion animation director (spec 2).
Pure and boring on purpose: classification lives in Python so the render
layer stays dumb and deterministic."""
import re

_NUM_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "hundred", "thousand", "million"}
_NEG = {"no", "not", "never", "nobody", "nothing", "stop", "wrong", "dead",
        "can't", "won't", "don't", "refuse", "refused", "quit"}
_POWER = {"fear", "afraid", "broke", "alone", "rich", "poor", "die", "death",
          "truth", "lie", "pain", "lost", "win", "fail", "weak", "strong",
          "enemy", "storm", "power", "control", "trapped", "free", "hunger",
          "silence", "empty", "brutal", "savage", "terrified", "coward"}
_HAS_DIGIT = re.compile(r"\d")


def _bare(w) -> str:
    return re.sub(r"[^\w']", "", str(w or "")).lower()


def classify_words(words: list) -> list:
    """Add a `cls` to every word dict. Priority: num > neg > power > end >
    stress > plain. Stress = longest bare word of each sentence. Never raises."""
    try:
        out = []
        # Sentence segmentation over word indices (terminal punctuation).
        sentence, sentences = [], []
        for i, wd in enumerate(words):
            sentence.append(i)
            if str(wd.get("w") or "").rstrip().endswith((".", "!", "?")):
                sentences.append(sentence)
                sentence = []
        if sentence:
            sentences.append(sentence)
        stress_idx = set()
        for sent in sentences:
            if sent:
                stress_idx.add(max(sent, key=lambda i: len(_bare(words[i].get("w")))))
        for i, wd in enumerate(words):
            raw = str(wd.get("w") or "")
            bare = _bare(raw)
            if _HAS_DIGIT.search(raw) or bare in _NUM_WORDS:
                cls = "num"
            elif bare in _NEG:
                cls = "neg"
            elif bare in _POWER:
                cls = "power"
            elif raw.rstrip().endswith((".", "!", "?")):
                cls = "end"
            elif i in stress_idx:
                cls = "stress"
            else:
                cls = "plain"
            out.append({**wd, "cls": cls})
        return out
    except Exception:  # noqa: BLE001 - garbage in -> all plain
        return [{**(w if isinstance(w, dict) else {}), "cls": "plain"}
                for w in (words or [])]
```

- [ ] **Step 4: Run** — 5 passed; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/video/word_classes.py tests/test_word_classes.py
git commit -m "feat(anim): per-word animation classifier (spec 2)"
```

### Task 3: Payload wiring — cls + animSeed

**Files:**
- Modify: `src/video/remotion_reel.py` (`write_bridge_file` gains `anim_seed: int = 0`; every wordTimes list passes through classify_words; `payload["animSeed"]`), `pipeline.py` (pass `anim_seed=row_n or 0` through `generate_remotion_reel` — add the passthrough param there too)
- Test: `tests/test_anim_payload.py`

**Interfaces:**
- Consumes: `classify_words` (Task 2).
- Produces: payload wordTimes entries carry `cls`; `payload["animSeed"]` int (written always, default 0). Remotion (Task 4/5) reads `wordTimes[scene][i].cls` and `animSeed`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_anim_payload.py
"""Bridge payload carries word classes + the deterministic anim seed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.remotion_reel import write_bridge_file


def test_wordtimes_classified_and_seed_written(tmp_path):
    p = tmp_path / "reel-data.json"
    write_bridge_file(
        hook="h", quote="q", attribution="— S", cta="c",
        mood="dark_philosophical", duration=10, fps=30, bridge_path=p,
        hook_words=[{"w": "Nobody", "start": 0.0, "end": 0.4},
                    {"w": "moved.", "start": 0.5, "end": 0.9}],
        anim_seed=42)
    d = json.loads(p.read_text())
    assert d["animSeed"] == 42
    assert d["wordTimes"]["hook"][0]["cls"] == "neg"
    assert d["wordTimes"]["hook"][1]["cls"] == "end"


def test_default_seed_zero(tmp_path):
    p = tmp_path / "reel-data.json"
    write_bridge_file(hook="h", quote="q", attribution="— S", cta="c",
                      mood="dark_philosophical", duration=10, fps=30,
                      bridge_path=p)
    assert json.loads(p.read_text())["animSeed"] == 0
```

- [ ] **Step 2: Run** — FAIL (`unexpected keyword argument 'anim_seed'`).

- [ ] **Step 3: Implement** — in `write_bridge_file`, add `anim_seed: int = 0` param; where `word_times` dict is assembled:

```python
    from src.video.word_classes import classify_words
    word_times = {k: classify_words(v) for k, v in word_times.items()}
```

(apply after the dict incl. optional bridge entry is built), and in the payload: `payload["animSeed"] = int(anim_seed)`. In `generate_remotion_reel`, add `anim_seed: int = 0` and forward it. In `pipeline.py` `_run_pov_reel`, pass `anim_seed=row_n or 0` at the `generate_remotion_reel` call.

- [ ] **Step 4: Run** — targeted + `tests/test_cinematic_wiring.py` + full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/video/remotion_reel.py pipeline.py tests/test_anim_payload.py
git commit -m "feat(anim): payload carries word classes + animSeed (spec 4)"
```

### Task 4: animDirector + AnimatedText effects

**Files:**
- Create: `remotion/src/lib/animDirector.ts`
- Modify: `remotion/src/lib/wordAt.ts` (`cls?: string` on WordTime), `remotion/src/components/AnimatedText.tsx`
- Test: `cd remotion && npx tsc --noEmit`

**Interfaces:**
- Consumes: `WordTime.cls`, `animSeed` (plumbed in Task 5).
- Produces: `type WordFx = "pop" | "pop2" | "shake" | "glowpop" | "countup" | "plain"`; `effectFor(cls: string | undefined, index: number, seed: number): WordFx`; `AnimatedText` prop `animSeed?: number` applying the effects per word from each word's REAL start frame.

- [ ] **Step 1: animDirector.ts**

```tsx
/** Deterministic per-word effect assignment (spec 3). Code is the director:
 *  class rules pick the technique, the seed varies flavor between reels. */
export type WordFx = "pop" | "pop2" | "shake" | "glowpop" | "countup" | "plain";

export function effectFor(
  cls: string | undefined,
  index: number,
  seed: number
): WordFx {
  switch (cls) {
    case "num":
      return "countup";
    case "neg":
      return "shake";
    case "power":
      return "glowpop";
    case "stress":
      return (seed + index) % 2 === 0 ? "pop" : "pop2";
    default:
      return "plain";
  }
}

/** Parse a countup target: integer ≤ 9999 (strip punctuation), else null. */
export function countupTarget(word: string): number | null {
  const m = word.replace(/[^\d]/g, "");
  if (!m) return null;
  const n = parseInt(m, 10);
  return Number.isFinite(n) && n <= 9999 ? n : null;
}
```

- [ ] **Step 2: wordAt.ts** — add `cls?: string;` to the WordTime interface (only change).

- [ ] **Step 3: AnimatedText.tsx** — add prop `animSeed?: number` (default 0). Inside the per-word map (words have `wordTimes[i]` when present): compute `const fx = effectFor(wordTimes[i]?.cls, i, animSeed);` and the word's real start frame `wf = wordTimes[i] ? Math.round(wordTimes[i].start * fps) : startFrame + i * staggerFrames;` then layer on top of the existing enter spring:

```tsx
          const local = frame - wf;                    // frames since word start
          let fxScale = 1, fxDx = 0, fxColor: string | null = null, fxGlow = 0;
          let display = word;
          if (fx === "pop" || fx === "pop2") {
            const amp = fx === "pop" ? 0.18 : 0.12;
            fxScale = 1 + amp * Math.max(0, 1 - Math.abs(local - 4) / 4);
            if (local >= 0 && local <= 8) fxColor = palette.accent;
          } else if (fx === "shake") {
            if (local >= 0 && local < 4) fxDx = (local % 2 === 0 ? 1 : -1) * 3;
          } else if (fx === "glowpop") {
            if (local >= 0 && local <= 10) { fxColor = palette.accent; fxGlow = 1; }
          } else if (fx === "countup") {
            const target = countupTarget(word);
            if (target !== null && local >= 0 && local < 8) {
              display = word.replace(/\d+/, String(Math.round((target * Math.min(1, local / 8)))));
            } else if (target === null && local >= 0 && local <= 8) {
              fxScale = 1 + 0.18 * Math.max(0, 1 - Math.abs(local - 4) / 4);  // pop fallback
            }
          }
```

Apply in the word's span style: multiply `fxScale` into the existing transform scale, add `translateX(${fxDx}px)`, use `fxColor ?? <existing color logic>`, and when `fxGlow` extend textShadow with `0 0 ${28 + 26 * fxGlow}px ${palette.glow}`. Render `{display}` instead of `{word}`. All clamped: negative `local` (word not yet spoken) → no effect.

- [ ] **Step 4: Type-check** — `cd remotion && npx tsc --noEmit` → clean.

- [ ] **Step 5: Commit**

```bash
git add remotion/src/lib/animDirector.ts remotion/src/lib/wordAt.ts remotion/src/components/AnimatedText.tsx
git commit -m "feat(anim): animation director + word effects in AnimatedText (spec 3)"
```

### Task 5: Scene-level effects + plumbing

**Files:**
- Modify: `remotion/src/PovReel.tsx` (animSeed prop + pass to scenes; ghost-trail in ramp window), `remotion/src/components/HookScene.tsx` + `BridgeScene.tsx` (forward `animSeed` to AnimatedText; BridgeScene sentence-end tick), `remotion/src/components/AnimatedQuote.tsx` (letter-cascade), `remotion/src/components/CtaScene.tsx` (freeze-pop; needs `voEndFrame?: number` prop from PovReel via voiceDurations.cta)
- Test: `cd remotion && npx tsc --noEmit`

**Interfaces:**
- Consumes: `effectFor`/`countupTarget` (Task 4); payload `animSeed` via PovReelProps.
- Produces: `PovReelProps.animSeed?: number`; `CtaScene` prop `voEndFrame?: number`; `BridgeScene`/`HookScene` prop `animSeed?: number`.

- [ ] **Step 1: PovReel.tsx** — add `animSeed?: number` to props + default 0; pass `animSeed` to HookScene/BridgeScene (and LoopPreview's HookScene). Ghost-trail: in the ramp window render the Quote scene's container twice — the echo copy wrapped in a div with `opacity: 0.3` and `transform: translateY(${(quoteStart - frame) * 0.8}px)` only when `frame >= quoteStart - 12 && frame < quoteStart` (guard `quoteStart > 0`). CtaScene gets `voEndFrame={voiceDurations.cta ? Math.round(voiceDurations.cta * fps) : undefined}`.

- [ ] **Step 2: HookScene/BridgeScene** — accept `animSeed?: number`, forward to `<AnimatedText ... animSeed={animSeed} />`. BridgeScene tick: when the ACTIVE chunk changes at a chunk whose first word has `cls === "end"`-terminated predecessor (i.e., previous chunk's last word cls is "end"), render a 2-frame `rgba(255,255,255,0.25)` AbsoluteFill flash at the chunk-start frame (`frame - chunkStart(active) < 2 && active > 0`).

- [ ] **Step 3: AnimatedQuote.tsx** — letter-cascade: when a word's `wordTimes` entry exists, replace the word's single reveal with per-letter spans whose opacity/translateY stagger across the word's real `[start, end]` span: letter `j` of `L` starts at `start + (end - start) * (j / L)` seconds. Keep the emphasis punch + karaoke color logic on the word level. Words without timings keep current behavior.

- [ ] **Step 4: CtaScene.tsx** — accept `voEndFrame?: number`; when set, at `frame ∈ [voEndFrame, voEndFrame + 8]` apply container scale `1 + 0.06 * (1 - |frame - voEndFrame - 4| / 4)` (freeze-pop after the words settle).

- [ ] **Step 5: Type-check + commit**

Run: `cd remotion && npx tsc --noEmit` → clean.

```bash
git add remotion/src/PovReel.tsx remotion/src/components/HookScene.tsx remotion/src/components/BridgeScene.tsx remotion/src/components/AnimatedQuote.tsx remotion/src/components/CtaScene.tsx
git commit -m "feat(anim): scene effects — cascade quote, end ticks, ghost trail, CTA freeze-pop (spec 3)"
```

### Task 6: Verification gate

- [ ] Full suite: `.venv/bin/python -m pytest -q` → green.
- [ ] `cd remotion && npx tsc --noEmit` → clean.
- [ ] Dry-run story render (detached; >10 min): `echo '{"row_number": 42}' > /tmp/seed.json && .venv/bin/python pipeline.py --remotion --dry-run --content /tmp/seed.json`. Then SYNC PROOF: read `remotion/public/reel-data.json` — pick a mid-bridge word, extract the video frame at `hookF/fps + word.start` seconds, assert that word is on screen (its chunk). Frame-check: a `power` or `stress` word at its start frame shows the accent color; a number (if present) renders.
- [ ] Punch dry-run: seed row 43 — duration still 7–20s, effects present.
- [ ] Push (`git pull --rebase --autostash && git push`). NEVER stage `data/pipeline.db`.
- [ ] Live acceptance at next open slot; Graph read-back + first comment.

## Self-Review (done)

- Spec coverage: 1→T1, 2→T2, 3→T4+T5, 4→T3, 5 (errors)→each task's fallbacks, 6 (testing)→per task + T6. No gaps.
- Placeholders: none; T5 steps are prose+exact formulas with all prop names pinned.
- Type consistency: `_alignment_to_words(text, alignment)` T1 only; `classify_words` T2=T3; `effectFor(cls, index, seed)`/`countupTarget` T4=T5 consumers; `animSeed` name identical across payload (T3), props (T4/T5); `WordTime.cls` T4 = payload `cls` T3.
