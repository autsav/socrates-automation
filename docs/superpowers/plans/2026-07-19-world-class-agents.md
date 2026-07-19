# World-Class Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade all live studio agents with expert playbooks + coded critique (Phase 1), then make the fleet learn from real Instagram engagement (Phase 2).

**Architecture:** Playbook constants compose into optimizer-managed prompts; story_writer runs 2 persona drafts picked by a deterministic rubric; director is retired in favor of a coded concept picker; Phase 2 re-polls Meta Insights into the existing `post_metrics` table, builds per-agent digests injected into agent calls, and adds a Thompson-sampling arc bandit gated behind a 20-post data floor.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), pytest, sqlite (`data/pipeline.db`), Anthropic API via `studio/client.py`, GitHub Actions cron.

## Global Constraints

- Never-crash contract: every new runtime stage is try/except best-effort with a safe fallback (spec: "Error handling").
- North-star metric: sends-per-reach = shares ÷ reach, reach floor 100 (spec 2.2).
- Judge is CODE, never a judge agent (spec: Locked decisions).
- `DAILY_SPEND_CEILING_USD = 5.0` (spec 1.5).
- Bandit activates only at ≥20 posts with metrics; below → static rotation (spec 2.3).
- `data/pipeline.db` committed copy must stay token-free: `git checkout -- data/pipeline.db` before every commit after any run.
- Run tests with `.venv/bin/python -m pytest`; keep files <500 lines.

## File Map

| File | Responsibility |
|---|---|
| `studio/playbooks.py` (new) | 5 expert-playbook string constants |
| `studio/rubric.py` (new) | `score_story(d) -> float`, `score_concept(hook, caption) -> float` — deterministic quality scoring |
| `studio/story_writer.py` (mod) | playbook + self-critique prompt; 2-draft persona generation picked by rubric |
| `studio/copywriter.py` (mod) | playbook + self-critique in draft prompt |
| `studio/trend_scout.py`, `studio/music_director.py`, `studio/strategist.py` (mod) | playbook lines in role defaults |
| `studio/concept_picker.py` (new) | code replacement for director: `pick_concept`, `build_decision` |
| `studio/run.py` (mod) | chain uses concept_picker, drops director |
| `studio/settings.py` (mod) | ceiling 5.0; director rows comment-marked legacy |
| `src/optimizer/assets.py` (mod) | drop `prompt.director.role` |
| `src/analytics/metrics.py` (mod) | `ingest_window()` re-polls posts 1–7 days old (upsert) |
| `src/analytics/performance_digest.py` (new) | `build_digest()`, `digest_text(view)` from post_metrics×posts |
| `src/analytics/arc_bandit.py` (new) | `pick(row_number, has_trend) -> str | None` Thompson sampling |
| `pipeline.py` (mod) | `_pick_arc` consults bandit first |
| `.github/workflows/optimizer.yml` (new) | weekly optimizer run → Telegram approval |
| `.github/workflows/analytics.yml` (mod) | calls `ingest_window` daily |

Digest injection note (deviation from spec 2.2 mechanics, same outcome): digests are appended to the **user message** of each agent call rather than a `{digest}` format-slot in role templates — stored champion prompts in `prompt_store` don't have the slot and `.format()` would KeyError on them.

---

## Phase 1 — Prompt Mastery

### Task 1: Playbooks module

**Files:**
- Create: `studio/playbooks.py`
- Test: `tests/test_playbooks.py`

**Interfaces:**
- Produces: `STORY_CRAFT`, `COPY_CRAFT`, `TREND_CRAFT`, `MUSIC_CRAFT`, `STRATEGY_CRAFT` — module-level `str` constants, each ≥400 chars, imported by Tasks 3–5.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_playbooks.py
"""Playbooks are the distilled domain expertise each agent's prompt embeds."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import playbooks


def test_all_playbooks_exist_and_are_substantial():
    for name in ("STORY_CRAFT", "COPY_CRAFT", "TREND_CRAFT",
                 "MUSIC_CRAFT", "STRATEGY_CRAFT"):
        text = getattr(playbooks, name)
        assert isinstance(text, str) and len(text) >= 400, name


def test_story_craft_covers_core_principles():
    t = playbooks.STORY_CRAFT.lower()
    for concept in ("escalat", "concrete", "twist", "send"):
        assert concept in t
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_playbooks.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'studio.playbooks'`

- [ ] **Step 3: Write the module**

```python
# studio/playbooks.py
"""Distilled domain-expert playbooks embedded in agent prompts (spec 1.1).
Module constants so tests can assert coverage and agents can compose them."""

STORY_CRAFT = (
    "NARRATIVE CRAFT (non-negotiable):\n"
    "- Open a curiosity gap in beat one and don't close it until the quote: the "
    "viewer must NEED the resolution.\n"
    "- Escalation ladder: every 1-2 sentences raise the stakes or the strangeness. "
    "Never repeat a beat at the same intensity.\n"
    "- Concrete-image rule: no abstraction where an image works. 'He ate stale "
    "bread on a marble floor' beats 'he practiced discomfort'.\n"
    "- The earned twist: the quote only lands if the story built its exact need. "
    "Pick the quote FIRST, then engineer the story toward it.\n"
    "- Send-psychology: the viewer shares to say something about THEMSELVES or "
    "their friend. End on a line that gives them those words.\n"
    "- Rhythm: short punchy sentences, a new mini-revelation every ~8 seconds."
)

COPY_CRAFT = (
    "COPY CRAFT (non-negotiable):\n"
    "- Statement hooks beat questions: assert something that sounds wrong, then "
    "prove it.\n"
    "- PAS captions: Problem (their words) -> Agitate (the cost tonight) -> Solve "
    "(the Stoic reframe).\n"
    "- First line <=8 words, curiosity gap, no hashtags — it is the only line "
    "shown before the fold.\n"
    "- Weave SEO keywords (discipline, stoic mindset, stop procrastinating) so "
    "naturally a reader never notices them.\n"
    "- One-reader rule: write to a single person at 2am, not an audience."
)

TREND_CRAFT = (
    "NEWSJACKING CRAFT (non-negotiable):\n"
    "- Recency beats importance: a 6-hour-old mid story outranks a 3-day-old big "
    "one.\n"
    "- The philosophy-bridge test: can a Stoic quote GENUINELY reframe this? If "
    "the bridge needs forcing, reject the trend — a forced bridge reads as spam.\n"
    "- Emotional charge beats scale: pick the story people are ARGUING about, "
    "not the biggest headline.\n"
    "- Specific numbers from the headline go in the hook verbatim."
)

MUSIC_CRAFT = (
    "SYNC SUPERVISION CRAFT (non-negotiable):\n"
    "- Energy-arc matching: the track's build must peak where the quote lands — "
    "search for builds, swells, drops; avoid flat loops.\n"
    "- Mood->instrument mapping: dark_philosophical = low strings/drones; "
    "cinematic_hopeful = piano+swell; epic_warrior = percussion.\n"
    "- Never vocal tracks under narration; melody fights the voice.\n"
    "- Under 90s reels, prefer tracks whose first 60s carry the full arc."
)

STRATEGY_CRAFT = (
    "POSITIONING CRAFT (non-negotiable):\n"
    "- The account promise: 'Short resets for people rebuilding discipline.' "
    "Every brief serves one of 3 pillars: trend/debate stories with a Stoic "
    "twist; weird philosophy history; the 3-line reset (funnel).\n"
    "- Audience-fatigue rotation: never brief the same audience twice in a row; "
    "check recent posts before choosing.\n"
    "- Specificity of pain: brief the 2am symptom ('reopened the app you just "
    "closed'), not the category ('procrastination')."
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_playbooks.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add studio/playbooks.py tests/test_playbooks.py
git commit -m "feat(agents): expert playbooks module (spec 1.1)"
```

### Task 2: Deterministic rubric

**Files:**
- Create: `studio/rubric.py`
- Test: `tests/test_rubric.py`

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces: `score_story(d: dict) -> float` (d has beat_hook/beat_reframe/beat_cta strings) and `score_concept(hook: str, caption: str) -> float`. Higher = better. Both never raise (malformed input → 0.0). Used by Task 3 (story pick) and Task 6 (concept pick).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric.py
"""The rubric IS the judge (spec: code judges, never a judge agent)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.rubric import score_story, score_concept


def _story(hook, reframe, cta):
    return {"beat_hook": hook, "beat_reframe": reframe, "beat_cta": cta}


def test_concrete_hook_beats_abstract():
    concrete = _story("He ate stale bread on a marble floor for 3 days.",
                      "One sentence. Another short one. Then a turn.",
                      "Send this to your most stubborn friend.")
    abstract = _story("Success is really about your mindset and growth.",
                      "One sentence. Another short one. Then a turn.",
                      "Send this to your most stubborn friend.")
    assert score_story(concrete) > score_story(abstract)


def test_specific_send_cta_beats_generic():
    a = _story("He owned one cup and threw it away.", "Short. Sharp. Turn.",
               "Send this to the friend who guards their stuff.")
    b = _story("He owned one cup and threw it away.", "Short. Sharp. Turn.",
               "Share this post.")
    assert score_story(a) > score_story(b)


def test_short_sentences_beat_run_ons():
    punchy = _story("Rome's richest man slept on dirt.",
                    "He did it monthly. Friends laughed. He trained. Fear lost.",
                    "Send this to someone scared of losing it all.")
    runon = _story("Rome's richest man slept on dirt.",
                   "He did it monthly and his friends laughed at him because they "
                   "did not understand that he was training so that fear would "
                   "eventually lose its grip on him entirely over time.",
                   "Send this to someone scared of losing it all.")
    assert score_story(punchy) > score_story(runon)


def test_never_raises_on_garbage():
    assert score_story({}) == 0.0
    assert score_story({"beat_hook": None}) == 0.0
    assert score_concept("", "") >= 0.0


def test_statement_concept_beats_question():
    assert score_concept("Discipline is a lie you tell daily.", "First line.\nBody") > \
           score_concept("Is discipline a lie you tell daily?", "First line.\nBody")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rubric.py -q`
Expected: FAIL `ModuleNotFoundError: No module named 'studio.rubric'`

- [ ] **Step 3: Implement**

```python
# studio/rubric.py
"""Deterministic quality scoring — the coded judge (spec 1.2).
Pure functions; higher is better; malformed input scores 0.0, never raises."""
import re

_ABSTRACTIONS = {
    "success", "mindset", "growth", "potential", "journey", "purpose",
    "greatness", "value", "energy", "abundance", "transformation",
}
_CONCRETE_HINTS = re.compile(
    r"\d|marble|bread|floor|barrel|rain|shoes|coin|cup|dirt|cloak|storm|2am|phone")
_SPECIFIC_CTA = re.compile(
    r"send this to (the|your|someone|a) ", re.I)


def _words(s):
    return re.findall(r"[A-Za-z']+", s or "")


def _sentence_lengths(text):
    parts = [p for p in re.split(r"[.!?]+", text or "") if p.strip()]
    return [len(_words(p)) for p in parts] or [0]


def score_story(d: dict) -> float:
    try:
        hook = d.get("beat_hook") or ""
        reframe = d.get("beat_reframe") or ""
        cta = d.get("beat_cta") or ""
        if not (hook and reframe and cta):
            return 0.0
        score = 0.0
        # Hook concreteness: images/numbers up, abstractions down.
        score += 2.0 * len(_CONCRETE_HINTS.findall(hook.lower()))
        score -= 1.5 * sum(w.lower() in _ABSTRACTIONS for w in _words(hook))
        if not hook.rstrip().endswith("?"):
            score += 1.0
        # Escalation rhythm: short mean sentence length in the story body.
        lens = _sentence_lengths(reframe)
        mean = sum(lens) / len(lens)
        score += max(0.0, 3.0 - (mean / 8.0))       # <=8-word sentences ideal
        score -= 1.0 * sum(w.lower() in _ABSTRACTIONS for w in _words(reframe)) / 10
        # CTA specificity: naming the receiver beats generic shares.
        if _SPECIFIC_CTA.search(cta):
            score += 2.0
        elif "send" in cta.lower():
            score += 0.5
        # Simplicity: penalize long words.
        all_words = _words(hook) + _words(reframe) + _words(cta)
        if all_words:
            long_frac = sum(len(w) > 8 for w in all_words) / len(all_words)
            score -= 3.0 * long_frac
        return round(score, 4)
    except Exception:  # noqa: BLE001 - judge must never crash the reel
        return 0.0


def score_concept(hook: str, caption: str) -> float:
    try:
        score = 0.0
        hook = hook or ""
        caption = caption or ""
        if hook and not hook.rstrip().endswith("?"):
            score += 1.0
        if len(_words(hook)) <= 12:
            score += 1.0
        score += 1.5 * len(_CONCRETE_HINTS.findall(hook.lower()))
        score -= 1.5 * sum(w.lower() in _ABSTRACTIONS for w in _words(hook))
        first = (caption.split("\n") or [""])[0]
        if 0 < len(_words(first)) <= 8:
            score += 1.0
        return round(score, 4)
    except Exception:  # noqa: BLE001
        return 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_rubric.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add studio/rubric.py tests/test_rubric.py
git commit -m "feat(agents): deterministic story/concept rubric — the coded judge (spec 1.2)"
```

### Task 3: story_writer — playbook, self-critique, 2-draft persona pick

**Files:**
- Modify: `studio/story_writer.py`
- Test: `tests/test_content_brains.py` (extend)

**Interfaces:**
- Consumes: `playbooks.STORY_CRAFT` (Task 1), `rubric.score_story` (Task 2).
- Produces: `write_story(client, mode, material, pool, extra_context="")` — same return contract (validated dict or None); NEW optional `extra_context` str appended to the user message (Task 9 digest injection uses it). `_PERSONAS` tuple of 2 strings.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_content_brains.py`)

```python
def test_write_story_two_drafts_rubric_picks_winner():
    calls = []

    class TwoDraftClient:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            base = {"quote_row": 7, "topic_query": "roman villa",
                    "caption_first_line": "He practiced losing everything.",
                    "trend_tag": "stoicism",
                    "beat_reframe": ('Seneca was one of the richest men in Rome. '
                                     * 12)[:900] + ' He trained. Fear lost.',
                    "beat_cta": "Send this to a friend ruled by fear."}
            if len(calls) == 1:   # draft A: abstract hook -> lower rubric score
                return dict(base, beat_hook="Success is about mindset and growth daily.")
            return dict(base, beat_hook="He slept on a marble floor for 3 nights.")

    out = write_story(TwoDraftClient(), "weird", {"hook_fact": "x"},
                      [{"row_number": 7, "quote": "q"}])
    assert out is not None
    assert out["beat_hook"].startswith("He slept")     # concrete draft won
    assert len(calls) == 2                              # exactly two drafts
    assert calls[0] != calls[1]                         # different personas


def test_write_story_extra_context_reaches_user_message():
    seen = {}

    class SpyClient:
        def call(self, role, prefix, role_system, user, schema):
            seen["user"] = user
            raise RuntimeError("stop after capture")

    write_story(SpyClient(), "weird", {"hook_fact": "x"},
                [{"row_number": 1, "quote": "q"}],
                extra_context="TOP PERFORMER: barefoot senator hook")
    assert "TOP PERFORMER" in seen["user"]


def test_story_prompt_embeds_playbook_and_critique():
    from studio import story_writer, playbooks
    assert playbooks.STORY_CRAFT in story_writer._ROLE_DEFAULT
    assert "critique" in story_writer._ROLE_DEFAULT.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_content_brains.py -q`
Expected: 3 new tests FAIL (`unexpected keyword argument 'extra_context'`, playbook assert).

- [ ] **Step 3: Implement in `studio/story_writer.py`**

Add import + personas, embed playbook + critique in `_ROLE_DEFAULT`, rewrite `write_story`:

```python
from studio import playbooks

_PERSONAS = (
    "Voice: a historian-screenwriter — cinematic scenes, period texture, "
    "the past made visible.",
    "Voice: a growth-storyteller — modern parallels, the viewer's own life "
    "mirrored in the ancient story.",
)
```

In `_ROLE_DEFAULT`, after the style-rules block and before the final length line, add:

```python
    + playbooks.STORY_CRAFT + "\n"
    "Before answering: draft internally, critique your draft against the "
    "craft rules above (hook concreteness, escalation, CTA specificity, "
    "simplicity), fix every weakness, then output ONLY the improved final "
    "JSON.\n"
```

Replace the body of `write_story`:

```python
def write_story(client, mode: str, material: dict, pool: list,
                extra_context: str = "") -> dict | None:
    """Two persona drafts -> rubric picks the winner (spec 1.2 B-lite).
    Returns validated dict or None (never raises)."""
    from studio.rubric import score_story
    try:
        role_tmpl = prompt_store.get("prompt.story_writer.role", _ROLE_DEFAULT)
        role = role_tmpl.format(
            mode=mode,
            material=json.dumps(material, ensure_ascii=False, indent=2),
            pool=json.dumps([{"row_number": p["row_number"], "quote": p["quote"]}
                             for p in pool[:20]], ensure_ascii=False, indent=2),
        )
        ctx = f"\n{extra_context}" if extra_context else ""
        drafts = []
        for persona in _PERSONAS:
            try:
                d = client.call("story_writer", _PREFIX, role,
                                f"Write the four beats now. {persona}{ctx}",
                                STORY_SCHEMA)
                ok, reason = validate_story(d or {})
                drafts.append((d, ok, reason))
            except Exception as e:  # noqa: BLE001 - one dead draft is fine
                drafts.append((None, False, str(e)))
        valid = [(score_story(d), d) for d, ok, _ in drafts if ok]
        if valid:
            valid.sort(key=lambda t: t[0], reverse=True)
            return valid[0][1]
        # Neither validated: corrective retry on draft A's failure reason.
        d0, _, reason = drafts[0]
        print(f"  [story_writer] both drafts rejected ({reason}) — retrying once")
        d = client.call("story_writer", _PREFIX, role,
                        f"Your last draft was rejected: {reason}. "
                        "Write the four beats again, fixing exactly that.",
                        STORY_SCHEMA)
        ok, reason = validate_story(d or {})
        if not ok:
            print(f"  [story_writer] rejected ({reason})")
            return None
        return d
    except Exception as e:  # noqa: BLE001 - never crash a reel
        print(f"  [story_writer] unavailable ({e})")
        return None
```

- [ ] **Step 4: Run the full content-brain tests**

Run: `.venv/bin/python -m pytest tests/test_content_brains.py tests/test_optimizer_wiring.py -q`
Expected: all pass (the wiring test still sees `prompt.story_writer.role` requested).
Note: `test_write_story_uses_client_and_validates` (existing) may now see two calls — update its FakeClient to tolerate repeated calls if it asserts call count.

- [ ] **Step 5: Commit**

```bash
git add studio/story_writer.py tests/test_content_brains.py
git commit -m "feat(story): playbook + inline self-critique + 2-persona drafts with rubric pick"
```

### Task 4: copywriter + trend_scout + music_director + strategist playbooks

**Files:**
- Modify: `studio/copywriter.py` (`_DRAFT_ROLE_DEFAULT`), `studio/trend_scout.py`, `studio/music_director.py`, `studio/strategist.py` (each `_ROLE_DEFAULT`/query default)
- Test: `tests/test_playbooks.py` (extend)

**Interfaces:**
- Consumes: Task 1 constants.
- Produces: each agent's default prompt contains its playbook; copywriter's also contains the critique instruction.

- [ ] **Step 1: Failing test** (append to `tests/test_playbooks.py`)

```python
def test_agent_defaults_embed_their_playbooks():
    import studio.copywriter as cw
    import studio.trend_scout as ts
    import studio.music_director as md
    import studio.strategist as st
    assert playbooks.COPY_CRAFT in cw._DRAFT_ROLE_DEFAULT
    assert "critique" in cw._DRAFT_ROLE_DEFAULT.lower()
    assert playbooks.TREND_CRAFT in ts._ROLE_DEFAULT
    assert playbooks.MUSIC_CRAFT in md._QUERY_ROLE_DEFAULT
    assert playbooks.STRATEGY_CRAFT in st._ROLE_DEFAULT
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_playbooks.py -q — expect the new test FAILS.`

- [ ] **Step 3: Implement** — in each module add `from studio import playbooks` and append the constant to the default prompt string. In copywriter's `_DRAFT_ROLE_DEFAULT` additionally append:

```python
    + "\nBefore answering: draft internally, critique against the copy craft "
    "rules, fix every weakness, output ONLY the improved final JSON.\n"
```

(Concatenate playbooks INSIDE the default string definitions so `prompt_store.get(key, default)` serves them as one asset; `.format()` slots like `{brief}`/`{n}` are unchanged — playbook text contains no braces.)

- [ ] **Step 4: Run full suite** — `.venv/bin/python -m pytest -q` — all pass (existing prompt-content tests may assert exact strings; update any that do).

- [ ] **Step 5: Commit**

```bash
git add studio/copywriter.py studio/trend_scout.py studio/music_director.py studio/strategist.py tests/test_playbooks.py
git commit -m "feat(agents): embed expert playbooks in copywriter/trend_scout/music_director/strategist"
```

### Task 5: Retire director — coded concept picker

**Files:**
- Create: `studio/concept_picker.py`
- Modify: `studio/run.py:4,24`, `src/optimizer/assets.py` (remove director row), `tests/test_optimizer_wiring.py` (drop `prompt.director.role` from set + the director test), `studio/settings.py` (comment-mark director rows legacy)
- Test: `tests/test_concept_picker.py`

**Interfaces:**
- Consumes: `rubric.score_concept` (Task 2); `Concept` and `Decision` dataclasses from `studio/types.py`; `AUDIENCE_TO_MOOD` from `src/core/excel_reader`.
- Produces: `pick_concept(concepts: list[Concept]) -> Concept` (rubric max, tie → first); `build_decision(concept, brief) -> Decision` with `scores=[]`, `top_pick=concept.id`, `alt_pick=None`, `revision={}`, `visual_direction={"mood": <from AUDIENCE_TO_MOOD or 'dark_philosophical'>, "flux_prompt": ""}`, `rationale="rubric pick"`. `run_studio` returns the same `(brief, decision, cmap)` tuple shape so `pipeline._studio_stage` is untouched.

- [ ] **Step 1: Failing test**

```python
# tests/test_concept_picker.py
"""Director retired (spec 1.4): code picks the concept, deterministically."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.concept_picker import pick_concept, build_decision
from studio.types import Concept


def _concept(cid, hook, caption="First line.\nBody text here."):
    return Concept(id=cid, hook=hook, caption=caption, reel_scenes=[],
                   rationale="", risk="")


class _Brief:
    audience = "stuck"
    quote = {"row_number": 1, "text": "q"}

    def to_dict(self):
        return {}


def test_concrete_statement_concept_wins():
    c = pick_concept([
        _concept("a", "Is success just mindset?"),
        _concept("b", "He threw away his only cup."),
    ])
    assert c.id == "b"


def test_tie_goes_to_first():
    c = pick_concept([_concept("a", "Same hook."), _concept("b", "Same hook.")])
    assert c.id == "a"


def test_build_decision_shape():
    d = build_decision(_concept("a", "Hook."), _Brief())
    assert d.top_pick == "a"
    assert d.visual_direction["mood"]
    assert d.revision == {}
```

NOTE: check `Concept` dataclass fields in `studio/types.py` before writing `_concept` — match its actual constructor exactly (adjust kwargs if fields differ; the pattern stands).

- [ ] **Step 2: Run to verify failure** — `ModuleNotFoundError: studio.concept_picker`.

- [ ] **Step 3: Implement**

```python
# studio/concept_picker.py
"""Code replacement for the retired director agent (spec 1.4): rubric picks
the concept; the Decision shape is preserved so downstream is untouched."""
from src.core.excel_reader import AUDIENCE_TO_MOOD
from studio.rubric import score_concept
from studio.types import Decision


def pick_concept(concepts):
    """Highest rubric score wins; ties go to the earliest (stable)."""
    return max(concepts, key=lambda c: (score_concept(c.hook, c.caption),
                                        -concepts.index(c)))


def build_decision(concept, brief) -> Decision:
    mood = AUDIENCE_TO_MOOD.get(getattr(brief, "audience", ""),
                                "dark_philosophical")
    return Decision(scores=[], top_pick=concept.id, alt_pick=None,
                    revision={}, visual_direction={"mood": mood,
                                                   "flux_prompt": ""},
                    rationale="rubric pick (director retired)")
```

In `studio/run.py`: replace `from studio import analyst, strategist, copywriter, director` with `from studio import analyst, strategist, copywriter, concept_picker` and replace the review line:

```python
        concept = concept_picker.pick_concept(concepts)
        decision = concept_picker.build_decision(concept, brief)
```

In `src/optimizer/assets.py`: delete the `prompt.director.role` row and the `import studio.director` line. In `tests/test_optimizer_wiring.py`: remove `"prompt.director.role"` from the expected set, delete `test_director_loads_prompt_via_store`, and drop `director` from the `_spy` module list. In `studio/settings.py`: suffix the two director rows with `# legacy — retired (spec 1.4)`.

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest tests/test_concept_picker.py tests/test_optimizer_wiring.py -q` then the full suite. Any existing studio-flow test that mocks `director.review` must be updated to the new chain.

- [ ] **Step 5: Commit**

```bash
git add studio/concept_picker.py studio/run.py src/optimizer/assets.py studio/settings.py tests/test_concept_picker.py tests/test_optimizer_wiring.py
git commit -m "feat(agents): retire director — deterministic concept picker (spec 1.4)"
```

### Task 6: Budget ceiling

**Files:**
- Modify: `studio/settings.py:43` (`DAILY_SPEND_CEILING_USD = 2.0` → `5.0`)

- [ ] **Step 1:** Edit the constant to `5.0` with comment `# raised for 2-draft + critique passes (spec 1.5)`.
- [ ] **Step 2:** Run `.venv/bin/python -m pytest -q -k "spend or ceiling"` — update any test pinning 2.0.
- [ ] **Step 3: Commit** — `git add studio/settings.py && git commit -m "feat(agents): raise studio spend ceiling to \$5/day (spec 1.5)"`

**PHASE 1 GATE:** full suite green; one live dry-run (`.venv/bin/python pipeline.py --remotion --dry-run`) completes with a story/weird arc reel; `git checkout -- data/pipeline.db`; push.

---

## Phase 2 — Learning Loop

### Task 7: Insights re-poll window

**Files:**
- Modify: `src/analytics/metrics.py` (add `ingest_window`), `.github/workflows/analytics.yml` (call it)
- Test: `tests/test_metrics_window.py`

**Interfaces:**
- Consumes: existing `fetch_post_metrics(post_id, access_token, ig_account_id) -> dict` and the existing `post_metrics` table (post_id, likes, comments, shares, reach, impressions, saved).
- Produces: `ingest_window(access_token, ig_account_id, db_path, days=7, dry_run=False) -> int` — for every live post 1–7 days old, fetch and UPSERT metrics (`INSERT OR REPLACE`), returning the number updated. Existing `ingest_pending` untouched.

- [ ] **Step 1: Failing test**

```python
# tests/test_metrics_window.py
"""Phase-2 poller: posts 1-7 days old get RE-polled (metrics keep moving)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import metrics


def _seed(db, post_id, days_ago, with_metrics=False):
    db.execute("INSERT INTO posts (post_id, posted_at, dry_run) "
               "VALUES (?, datetime('now', ?), 0)", (post_id, f"-{days_ago} days"))
    if with_metrics:
        db.execute("INSERT INTO post_metrics (post_id, shares, reach) "
                   "VALUES (?, 1, 100)", (post_id,))


def test_window_repolls_and_upserts(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE posts (post_id TEXT, posted_at TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, likes INT "
               "DEFAULT 0, comments INT DEFAULT 0, shares INT DEFAULT 0, "
               "reach INT DEFAULT 0, impressions INT DEFAULT 0, saved INT DEFAULT 0)")
    _seed(db, "fresh", 2, with_metrics=True)   # has stale metrics -> re-polled
    _seed(db, "old", 12)                        # outside window -> skipped
    db.commit(); db.close()

    monkeypatch.setattr(metrics, "fetch_post_metrics",
                        lambda pid, tok, ig: {"likes": 9, "comments": 1,
                                              "shares": 5, "reach": 200,
                                              "impressions": 250, "saved": 3})
    n = metrics.ingest_window("tok", "ig", db_path=db_path)
    assert n == 1
    row = sqlite3.connect(db_path).execute(
        "SELECT shares, reach FROM post_metrics WHERE post_id='fresh'").fetchone()
    assert row == (5, 200)
```

- [ ] **Step 2: Run** — FAIL `AttributeError: ingest_window`.

- [ ] **Step 3: Implement** in `src/analytics/metrics.py` (match the module's existing sqlite style):

```python
def ingest_window(access_token, ig_account_id, db_path, days=7, dry_run=False):
    """Re-poll every live post 1-{days} days old and upsert its metrics —
    engagement keeps moving for a week, one snapshot at 24h under-counts
    sends (spec 2.1). Returns the number of posts updated."""
    import sqlite3
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT post_id FROM posts WHERE post_id IS NOT NULL AND dry_run=0 "
            "AND posted_at <= datetime('now', '-1 day') "
            "AND posted_at >= datetime('now', ?)", (f"-{days} days",)).fetchall()
        updated = 0
        for (post_id,) in rows:
            if dry_run:
                print(f"    [dry-run] would re-poll {post_id}")
                continue
            try:
                m = fetch_post_metrics(post_id, access_token, ig_account_id)
            except Exception as e:  # noqa: BLE001 - one dead post never stops the sweep
                print(f"    [analytics] {post_id} failed ({e}) — skipping")
                continue
            con.execute(
                "INSERT OR REPLACE INTO post_metrics "
                "(post_id, likes, comments, shares, reach, impressions, saved) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (post_id, m.get("likes", 0), m.get("comments", 0),
                 m.get("shares", 0), m.get("reach", 0),
                 m.get("impressions", 0), m.get("saved", 0)))
            updated += 1
        con.commit()
        return updated
    finally:
        con.close()
```

In `.github/workflows/analytics.yml`, after the existing ingest step, add a step running (mirror the existing step's env exactly):

```yaml
      - name: Re-poll 7-day window
        run: python -c "from src.analytics.metrics import ingest_window; import os; print(ingest_window(os.environ['META_ACCESS_TOKEN'], os.environ['IG_ACCOUNT_ID'], 'data/pipeline.db'))"
```

- [ ] **Step 4: Run** — test passes; full suite green.
- [ ] **Step 5: Commit** — `git add src/analytics/metrics.py .github/workflows/analytics.yml tests/test_metrics_window.py && git commit -m "feat(loop): 7-day insights re-poll window (spec 2.1)"`

### Task 8: Performance digest

**Files:**
- Create: `src/analytics/performance_digest.py`
- Test: `tests/test_performance_digest.py`

**Interfaces:**
- Consumes: `posts` (post_id, arc, hook/caption columns — check actual column names in `data_store.init_db` before coding; the plan assumes `posts.arc` exists and hook/caption live in `posts.versions` JSON or columns) and `post_metrics`.
- Produces: `build_digest(db_path) -> dict` with keys `story_writer`, `copywriter`, `strategist`, each a list of `{"rank": "top"|"bottom", "arc": str, "hook": str, "sends_per_reach": float}`; `digest_text(view: str, db_path=DEFAULT) -> str` — human-readable block, `"No performance data yet."` when empty or on ANY exception (cold-start safe). Reach floor 100.

- [ ] **Step 1: Failing test**

```python
# tests/test_performance_digest.py
"""Per-agent digest: agents SEE their own results (spec 2.2)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.performance_digest import build_digest, digest_text


def _db(tmp_path):
    p = tmp_path / "t.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE posts (post_id TEXT, arc TEXT, hook TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, shares INT, reach INT)")
    rows = [("p1", "weird", "Barefoot senator.", 9, 300),    # 3.0% -> top
            ("p2", "story", "Airport chaos.", 2, 400),        # 0.5%
            ("p3", "classic", "Plain quote.", 0, 500),        # 0.0% -> bottom
            ("p4", "weird", "Tiny reach.", 50, 50)]           # under floor -> excluded
    for pid, arc, hook, sh, re_ in rows:
        db.execute("INSERT INTO posts VALUES (?, ?, ?, 0)", (pid, arc, hook))
        db.execute("INSERT INTO post_metrics VALUES (?, ?, ?)", (pid, sh, re_))
    db.commit(); db.close()
    return p


def test_ranks_by_sends_per_reach_with_floor(tmp_path):
    d = build_digest(_db(tmp_path))
    sw = d["story_writer"]
    assert sw[0]["hook"] == "Barefoot senator." and sw[0]["rank"] == "top"
    assert all(e["hook"] != "Tiny reach." for e in sw)


def test_digest_text_cold_start(tmp_path):
    p = tmp_path / "empty.db"
    sqlite3.connect(p).close()
    assert digest_text("story_writer", db_path=p) == "No performance data yet."
```

- [ ] **Step 2: Run** — FAIL ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/analytics/performance_digest.py
"""Per-agent performance digests over posts x post_metrics (spec 2.2).
sends-per-reach is the north star; reach floor kills small-sample noise."""
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "pipeline.db"
CACHE = DEFAULT_DB.parent / "perf_digest.json"
REACH_FLOOR = 100
TOP_N = 3


def _rows(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        return con.execute(
            "SELECT p.arc, p.hook, m.shares, m.reach FROM posts p "
            "JOIN post_metrics m ON p.post_id = m.post_id "
            "WHERE p.dry_run=0 AND m.reach >= ?", (REACH_FLOOR,)).fetchall()
    finally:
        con.close()


def build_digest(db_path=DEFAULT_DB) -> dict:
    try:
        scored = sorted(
            ({"arc": arc or "?", "hook": hook or "",
              "sends_per_reach": round(shares / reach, 4)}
             for arc, hook, shares, reach in _rows(db_path) if reach),
            key=lambda e: e["sends_per_reach"], reverse=True)
        if not scored:
            return {}
        top = [dict(e, rank="top") for e in scored[:TOP_N]]
        bottom = [dict(e, rank="bottom") for e in scored[-TOP_N:]
                  if e not in scored[:TOP_N]]
        view = top + bottom
        digest = {"story_writer": view, "copywriter": view, "strategist": view}
        try:
            CACHE.write_text(json.dumps(digest, indent=2))
        except Exception:  # noqa: BLE001 - cache is best-effort
            pass
        return digest
    except Exception:  # noqa: BLE001 - digest must never break generation
        return {}


def digest_text(view: str, db_path=DEFAULT_DB) -> str:
    d = build_digest(db_path).get(view) or []
    if not d:
        return "No performance data yet."
    lines = ["Recent performance (sends-per-reach — copy what wins, avoid what dies):"]
    for e in d:
        lines.append(f"- [{e['rank']}] {e['sends_per_reach']:.1%} | arc={e['arc']} "
                     f"| hook: {e['hook'][:80]}")
    return "\n".join(lines)
```

NOTE: verify `posts` column names (`arc`, and where the hook lives — if hook is inside `posts.versions` JSON, parse it; adjust `_rows` and the test schema to the real schema in `src/core/data_store.py:60-115`).

- [ ] **Step 4: Run** — both tests pass; full suite green.
- [ ] **Step 5: Commit** — `git add src/analytics/performance_digest.py tests/test_performance_digest.py && git commit -m "feat(loop): per-agent performance digest (spec 2.2)"`

### Task 9: Digest injection into agent calls

**Files:**
- Modify: `pipeline.py` `_build_story_beats` (pass `extra_context=digest_text("story_writer")`), `studio/run.py` (append `digest_text("copywriter")` to copywriter's user message via a new optional arg on `copywriter.draft`, same pattern for `strategist.make_brief`)
- Test: `tests/test_digest_injection.py`

**Interfaces:**
- Consumes: `digest_text(view)` (Task 8), `write_story(..., extra_context=...)` (Task 3).
- Produces: `copywriter.draft(client, perf, brief, n=..., extra_context="")` and `strategist.make_brief(client, perf, slot, recent_posts, pool, extra_context="")` — appended to their user messages when non-empty.

- [ ] **Step 1: Failing test**

```python
# tests/test_digest_injection.py
"""Every writer agent sees what actually performed (spec 2.2/C)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import studio.copywriter as copywriter


class _Perf:
    def to_dict(self):
        return {}


class _Brief:
    def to_dict(self):
        return {"quote": "q", "audience": "a"}


def test_copywriter_appends_digest_to_user_message():
    seen = {}

    class Spy:
        def call(self, role, prefix, role_system, user, schema):
            seen["user"] = user
            return {"concepts": []}

    copywriter.draft(Spy(), _Perf(), _Brief(), n=1,
                     extra_context="Recent performance: X wins")
    assert "Recent performance: X wins" in seen["user"]


def test_empty_context_leaves_message_unchanged():
    seen = {}

    class Spy:
        def call(self, role, prefix, role_system, user, schema):
            seen["user"] = user
            return {"concepts": []}

    copywriter.draft(Spy(), _Perf(), _Brief(), n=1)
    assert seen["user"] == "Write the concepts now."
```

- [ ] **Step 2: Run** — FAIL (unexpected keyword `extra_context`).

- [ ] **Step 3: Implement** — in `copywriter.draft` add the parameter and:

```python
    user = "Write the concepts now."
    if extra_context:
        user += f"\n{extra_context}"
    data = client.call("copywriter", shared_prefix(perf), role, user,
                       CONCEPTS_SCHEMA)
```

Mirror in `strategist.make_brief`. In `studio/run.py`:

```python
        from src.analytics.performance_digest import digest_text
        try:
            cw_digest = digest_text("copywriter")
            st_digest = digest_text("strategist")
        except Exception:  # noqa: BLE001 - digest optional
            cw_digest = st_digest = ""
        brief = strategist.make_brief(client, perf, slot, recent_posts, pool,
                                      extra_context=st_digest)
        concepts = copywriter.draft(client, perf, brief, extra_context=cw_digest)
```

In `pipeline.py` `_build_story_beats`, before `write_story`:

```python
        try:
            from src.analytics.performance_digest import digest_text
            extra = digest_text("story_writer")
        except Exception:  # noqa: BLE001
            extra = ""
        story = write_story(client, mode, material, pool, extra_context=extra)
```

- [ ] **Step 4: Run full suite.** Existing strategist tests calling `make_brief` positionally are unaffected (new arg is keyword-with-default).
- [ ] **Step 5: Commit** — `git add studio/copywriter.py studio/strategist.py studio/run.py pipeline.py tests/test_digest_injection.py && git commit -m "feat(loop): inject performance digest into writer agents (spec 2.2 + C)"`

### Task 10: Arc bandit

**Files:**
- Create: `src/analytics/arc_bandit.py`
- Modify: `pipeline.py` `_pick_arc`
- Test: `tests/test_arc_bandit.py`

**Interfaces:**
- Consumes: `posts.arc` + `post_metrics` (shares, reach).
- Produces: `pick(row_number: int | None, has_trend: bool, db_path=DEFAULT) -> str | None` — None below the 20-post floor or on any error; otherwise an arc name from the availability set (`{"story","weird","classic","question","cold_open"}` with trend; no `story`-requires-trend distinction needed — story falls back to debate material without a trend). Deterministic for a given (db state, row_number): RNG seeded with `row_number or 0`.

- [ ] **Step 1: Failing test**

```python
# tests/test_arc_bandit.py
"""Thompson sampling over arcs on sends-per-reach (spec 2.3)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import arc_bandit


def _db(tmp_path, n_per_arc):
    p = tmp_path / "t.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE posts (post_id TEXT, arc TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, shares INT, reach INT)")
    i = 0
    for arc, shares in n_per_arc:
        pid = f"p{i}"; i += 1
        db.execute("INSERT INTO posts VALUES (?, ?, 0)", (pid, arc))
        db.execute("INSERT INTO post_metrics VALUES (?, ?, 200)", (pid, shares))
    db.commit(); db.close()
    return p


def test_below_floor_returns_none(tmp_path):
    p = _db(tmp_path, [("weird", 5)] * 5)
    assert arc_bandit.pick(1, True, db_path=p) is None


def test_dominant_arc_wins_most_rows(tmp_path):
    rows = [("weird", 10)] * 12 + [("classic", 0)] * 12   # weird crushes classic
    p = _db(tmp_path, rows)
    picks = [arc_bandit.pick(r, True, db_path=p) for r in range(30)]
    assert picks.count("weird") > picks.count("classic")


def test_deterministic_per_row(tmp_path):
    p = _db(tmp_path, [("weird", 10)] * 12 + [("classic", 0)] * 12)
    assert arc_bandit.pick(7, True, db_path=p) == arc_bandit.pick(7, True, db_path=p)
```

- [ ] **Step 2: Run** — FAIL ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/analytics/arc_bandit.py
"""Thompson-sampling arc selection on sends-per-reach (spec 2.3).
A post is a 'hit' when its sends-per-reach beats the global median; each arc
gets Beta(1+hits, 1+misses). Deterministic per row (seeded RNG) so tests and
reruns reproduce. Below DATA_FLOOR scored posts -> None (static rotation)."""
import random
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "pipeline.db"
DATA_FLOOR = 20
ARCS = ("story", "weird", "classic", "question", "cold_open")


def _scores(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        return [(arc, shares / reach) for arc, shares, reach in con.execute(
            "SELECT p.arc, m.shares, m.reach FROM posts p "
            "JOIN post_metrics m ON p.post_id = m.post_id "
            "WHERE p.dry_run=0 AND p.arc IS NOT NULL AND m.reach >= 100")
            if reach]
    finally:
        con.close()


def pick(row_number, has_trend, db_path=DEFAULT_DB):
    try:
        scores = _scores(db_path)
        if len(scores) < DATA_FLOOR:
            return None
        med = sorted(s for _, s in scores)[len(scores) // 2]
        rng = random.Random(row_number or 0)
        best, best_draw = None, -1.0
        for arc in ARCS:
            hits = sum(1 for a, s in scores if a == arc and s > med)
            miss = sum(1 for a, s in scores if a == arc and s <= med)
            draw = rng.betavariate(1 + hits, 1 + miss)
            if draw > best_draw:
                best, best_draw = arc, draw
        return best
    except Exception:  # noqa: BLE001 - bandit failure -> static rotation
        return None
```

In `pipeline.py` `_pick_arc`, prepend:

```python
def _pick_arc(row_number: int | None, has_trend: bool = False) -> str:
    try:
        from src.analytics.arc_bandit import pick as _bandit_pick
        chosen = _bandit_pick(row_number, has_trend)
        if chosen:
            return chosen
    except Exception:  # noqa: BLE001 - bandit optional
        pass
    rot = _ARC_ROTATION_TREND if has_trend else _ARC_ROTATION_NO_TREND
    return rot[(row_number or 0) % len(rot)]
```

- [ ] **Step 4: Run** — bandit tests + `tests/test_viral_arcs.py` (rotation tests must still pass: the committed test DB has <20 scored posts so `pick` returns None in the suite).
- [ ] **Step 5: Commit** — `git add src/analytics/arc_bandit.py pipeline.py tests/test_arc_bandit.py && git commit -m "feat(loop): Thompson-sampling arc bandit behind 20-post floor (spec 2.3)"`

### Task 11: Weekly optimizer cadence

**Files:**
- Create: `.github/workflows/optimizer.yml`, `scripts/run_optimizer.py`
- Test: `tests/test_run_optimizer.py`

**Interfaces:**
- Consumes: `src/optimizer/loop.run_once(client, perf_context, ...)` and `loop.evaluate_experiments()`; `performance_digest.digest_text` as `perf_context`; `StudioClient(cfg.ANTHROPIC_API_KEY)`.
- Produces: `scripts/run_optimizer.py` with `main(dry_run=False) -> int` (number of proposals emitted); workflow schedules it Mondays 08:00 UTC.

- [ ] **Step 1: Failing test**

```python
# tests/test_run_optimizer.py
"""Weekly cadence entrypoint wires digest -> critic (spec 2.4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import run_optimizer


def test_main_passes_digest_as_perf_context(monkeypatch):
    captured = {}
    monkeypatch.setattr(run_optimizer, "_digest", lambda: "DIGEST BLOCK")
    monkeypatch.setattr(run_optimizer.loop, "evaluate_experiments", lambda: [])
    monkeypatch.setattr(run_optimizer.loop, "run_once",
                        lambda client, perf_context, **kw:
                        captured.setdefault("ctx", perf_context) or [])
    monkeypatch.setattr(run_optimizer, "_client", lambda: object())
    run_optimizer.main(dry_run=True)
    assert captured["ctx"] == "DIGEST BLOCK"
```

(`scripts/` needs an `__init__.py` if absent for the import to work.)

- [ ] **Step 2: Run** — FAIL ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# scripts/run_optimizer.py
"""Weekly optimizer entrypoint (spec 2.4): evaluate running experiments, then
let prompt_critic propose challengers with REAL performance context."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import loop


def _digest():
    from src.analytics.performance_digest import digest_text
    return digest_text("story_writer")


def _client():
    from config import Config
    from studio.client import StudioClient
    return StudioClient(Config().ANTHROPIC_API_KEY)


def main(dry_run=False) -> int:
    promoted = loop.evaluate_experiments()
    print(f"[optimizer] experiments evaluated: {promoted}")
    proposals = loop.run_once(_client(), _digest()) or []
    for p in proposals:
        print(loop.format_proposal_message(p))
    if dry_run:
        print(f"[optimizer] dry-run: {len(proposals)} proposal(s), not queued")
    return len(proposals)


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
```

NOTE: check `loop.run_once`'s exact signature/return at `src/optimizer/loop.py:81` before wiring — adapt the call (and Telegram queueing, which run_once may already handle via proposals table + approval_daemon) to what it actually does.

```yaml
# .github/workflows/optimizer.yml
name: Weekly prompt optimizer
on:
  schedule:
    - cron: "0 8 * * 1"
  workflow_dispatch: {}
jobs:
  optimize:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - name: Run optimizer
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/run_optimizer.py
```

- [ ] **Step 4: Run** — test passes; `python scripts/run_optimizer.py --dry-run` locally exits 0.
- [ ] **Step 5: Commit** — `git add scripts/run_optimizer.py .github/workflows/optimizer.yml tests/test_run_optimizer.py scripts/__init__.py && git commit -m "feat(loop): weekly optimizer cadence with digest-fed critic (spec 2.4)"`

### Task 12: Phase 2 gate — verification

- [ ] Full suite green: `.venv/bin/python -m pytest -q` (expect ~690+).
- [ ] Live dry-run: `.venv/bin/python pipeline.py --remotion --dry-run` — story/weird arc renders; log shows `story_writer` two-draft pick; no crash with empty digest ("No performance data yet." path).
- [ ] `git checkout -- data/pipeline.db` (token scrub) then `git push`.
- [ ] Live acceptance (next open slot): one post publishes; confirm digest injection did not alter the posting path; verify first-comment still attaches (Graph read-back).
- [ ] Manual follow-ups to note for the user: none required until ≥20 posts have metrics (bandit self-activates); optimizer proposals arrive in Telegram Mondays.

## Self-Review (done)

- Spec coverage: 1.1→T1, 1.2→T2+T3, 1.3→T3+T4, 1.4→T5, 1.5→T6, 2.1→T7, 2.2→T8+T9, C→T8/T9, 2.3→T10, 2.4→T11, error-handling+testing→each task + T12. No gaps.
- Placeholders: none; two explicit VERIFY notes (Concept fields in T5, posts schema in T8, run_once signature in T11) are instructions to check real code, with the pattern supplied.
- Type consistency: `score_story(d) -> float` used in T3; `digest_text(view)` in T9/T11; `extra_context` kwarg consistent across T3/T9; `pick(row_number, has_trend, db_path)` consistent in T10.
