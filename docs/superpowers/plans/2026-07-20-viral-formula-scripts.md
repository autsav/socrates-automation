# Viral-Formula Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scripts become viewer-first double-loop 60s stories enforced by a deterministic formula validator with in-prompt exemplars, and material repetition dies via a 60-capsule pool with last-20 tracking.

**Architecture:** `validate_formula` gates both persona drafts (after `validate_story`, before rubric) for story/weird/debate modes; the prompt embeds the 6-phase formula + two exemplar scripts; `weird_stories` grows to ≥60 keyed capsules; `pick_weird`/`pick_debate` accept an `exclude` set fed from a new `posts.material_key` column (last-20, LRU fallback).

**Tech Stack:** Python 3.11 (`.venv/bin/python`), pytest, sqlite additive migration.

## Global Constraints

- Formula checks apply to story/weird/debate modes only; punch mode SKIPS `validate_formula` (spec 4).
- Word budgets unchanged: total 140–215, reframe ≤185; punch 25–60 (existing).
- Never-crash: formula rejection → existing corrective retry (reason string) → fallback arc; tracking failure → empty exclude set; pickers never return None.
- Capsules: ≥60 total, every one historically attested with `source_note`, unique `key` slug, `send_cta` containing "Send this", passes `is_unsafe` + `mentions_named_person`.
- Exclusion: last-20 posts' material_keys; all-excluded → least-recently-used (deterministic).
- `data/pipeline.db` is NOT tracked — never `git add` it.
- Both exemplar scripts MUST pass `validate_formula` (tested by importing them).
- Tests via `.venv/bin/python -m pytest`; files <500 lines (weird_stories may approach it — if >500, split capsules into `weird_capsules_data.py` imported by `weird_stories.py`).

## File Map

| File | Responsibility |
|---|---|
| `studio/story_writer.py` (mod) | `validate_formula`, `EXEMPLAR_WEIRD`/`EXEMPLAR_DEBATE` constants, formula prompt rewrite, gate wiring in `write_story` |
| `src/content/weird_stories.py` (mod, possibly + `weird_capsules_data.py`) | ≥60 keyed capsules; `pick_weird(row, exclude=frozenset())` |
| `src/content/debate_topics.py` (mod) | topic `key` slugs; `pick_debate(row, exclude=frozenset())` |
| `src/core/data_store.py` (mod) | `posts.material_key` additive migration; `record_material(row_id, key)` |
| `pipeline.py` (mod) | `_build_story_beats` builds exclude + stamps `story["material_key"]`; `record_material` call beside `record_arc` (line ~1183) |

---

### Task 1: validate_formula + exemplars + prompt rewrite

**Files:**
- Modify: `studio/story_writer.py`
- Test: `tests/test_viral_formula.py`

**Interfaces:**
- Consumes: existing `validate_story(d, min_total, mode)`, `_ROLE_DEFAULT` (format slots {mode}/{material}/{pool}), `write_story` 2-draft loop.
- Produces: `validate_formula(d: dict) -> tuple[bool, str]` (True/"ok" or False/reason); module constants `EXEMPLAR_WEIRD: dict` and `EXEMPLAR_DEBATE: dict` (full beat dicts); `write_story` gates each draft with `validate_story(...) AND (mode == "punch" or validate_formula(...))`, retry message carries whichever reason failed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_viral_formula.py
"""The 6-phase viral formula, enforced by code (spec 1+2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.story_writer import (
    validate_formula, EXEMPLAR_WEIRD, EXEMPLAR_DEBATE, _ROLE_DEFAULT)


def _script(hook, reframe, cta="Send this to the friend who needs it most."):
    return {"beat_hook": hook, "beat_reframe": reframe, "quote_row": 1,
            "beat_cta": cta, "topic_query": "man storm",
            "caption_first_line": "Read this twice."}


GOOD_REFRAME = (
    "You know that thing you replay at 2am. The loss you never talk about. "
    "Now meet a merchant named Zeno. Everything he owned sat in one ship's hold. "
    "Purple dye. A fortune. One storm took all of it to the bottom of the sea. "
    "He washed up in Athens with nothing. Forty years old. Ruined. "
    "And nobody expected what he did next. He walked into a bookshop, dripping "
    "wet, and started reading. Then he stopped leaving. He gave up rebuilding "
    "the fortune. He sat in a painted porch and started talking about what "
    "storms cannot take. Strangers gathered. Kings sent letters. The porch "
    "became a school. The school became Stoicism. Twenty-three centuries later "
    "you are still hearing about it. His shipwreck built more than his ships "
    "ever carried.")


def test_happy_path_passes():
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        GOOD_REFRAME))
    assert ok, r


def test_hook_must_address_viewer():
    ok, r = validate_formula(_script(
        "A rich merchant lost everything in a storm.", GOOD_REFRAME))
    assert not ok and "viewer" in r


def test_hook_must_not_resolve():
    ok, r = validate_formula(_script(
        "Here's how you stop losing: the answer is Stoicism.", GOOD_REFRAME))
    assert not ok


def test_stakes_need_second_person_early():
    third_person = GOOD_REFRAME.replace("You know that thing you replay at 2am. "
                                        "The loss you never talk about. ", "")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        third_person))
    assert not ok and "second person" in r


def test_no_early_resolution_vocab():
    spoiled = GOOD_REFRAME.replace("One storm took",
                                   "The lesson is simple. One storm took")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        spoiled))
    assert not ok and "resolution" in r


def test_cliffhanger_marker_required():
    flat = GOOD_REFRAME.replace("And nobody expected what he did next. ", "") \
                       .replace("Then he stopped leaving. ", "")
    ok, r = validate_formula(_script(
        "You lost something this year you're still pretending doesn't hurt.",
        flat))
    assert not ok and "cliffhanger" in r


def test_exemplars_pass_their_own_formula():
    for ex in (EXEMPLAR_WEIRD, EXEMPLAR_DEBATE):
        ok, r = validate_formula(ex)
        assert ok, r


def test_prompt_embeds_formula_and_exemplars():
    t = _ROLE_DEFAULT.lower()
    assert "open loop" in t and "cliffhanger" in t
    assert EXEMPLAR_WEIRD["beat_hook"] in _ROLE_DEFAULT
    assert EXEMPLAR_DEBATE["beat_hook"] in _ROLE_DEFAULT
    assert '"lesson"' in t or "the word 'lesson' is banned" in t or "banned" in t
```

- [ ] **Step 2: Run** — `.venv/bin/python -m pytest tests/test_viral_formula.py -q` → FAIL ImportError.

- [ ] **Step 3: Implement** in `studio/story_writer.py`:

```python
_RESOLUTION_PHRASES = ("that's why", "the answer", "here's how", "the lesson",
                       "this means", "the secret is")
_CLIFFHANGER_STARTS = ("then ", "until ", "but ", "and nobody", "and no one")


def validate_formula(d: dict) -> tuple[bool, str]:
    """The 6-phase viral formula, deterministically (spec 2). Runs AFTER
    validate_story; story/weird/debate modes only."""
    try:
        hook = (d.get("beat_hook") or "").strip()
        reframe = (d.get("beat_reframe") or "").strip()
        hl = hook.lower()
        if not ("you" in hl.split() or "your" in hl.split() or
                "you're" in hl.split() or "you've" in hl.split()):
            return False, "hook must address the viewer (you/your)"
        if any(p in hl for p in _RESOLUTION_PHRASES):
            return False, "hook resolves its own loop"
        words = reframe.split()
        if not words:
            return False, "empty reframe"
        first25 = " ".join(words[:25]).lower()
        if not any(t in first25.split() or t in first25
                   for t in ("you", "your", "you're", "you've")):
            return False, "stakes phase needs second person in the first 25 words"
        two_thirds = " ".join(words[: (2 * len(words)) // 3]).lower()
        if any(p in two_thirds for p in _RESOLUTION_PHRASES):
            return False, "resolution vocabulary before the payoff phase"
        third = len(words) // 3
        middle = " ".join(words[third: 2 * third]).lower()
        sentences = [s.strip() for s in middle.replace("!", ".").replace("?", ".").split(".")]
        # A sentence STARTING with an unresolved-turn marker; also accept the
        # marker appearing right after a sentence break anywhere mid-text.
        has_cliff = any(s.startswith(_CLIFFHANGER_STARTS) or
                        s.startswith(("and nobody", "and no one"))
                        for s in sentences if s)
        if not has_cliff:
            return False, "cliffhanger marker missing from the middle third"
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, f"malformed: {e}"
```

Exemplar constants (verbatim — these are the taste-teachers, and the test imports them):

```python
EXEMPLAR_WEIRD = {
    "beat_hook": "You lost something this year you're still pretending doesn't hurt.",
    "beat_reframe": (
        "You know that thing you replay at 2am. The loss you never talk about. "
        "Now meet a merchant named Zeno. Everything he owned sat in one ship's hold. "
        "Purple dye. A fortune. One storm took all of it to the bottom of the sea. "
        "He washed up in Athens with nothing. Forty years old. Ruined. "
        "And nobody expected what he did next. He walked into a bookshop, dripping "
        "wet, and started reading. Then he stopped leaving. He gave up rebuilding "
        "the fortune. He sat in a painted porch and started talking about what "
        "storms cannot take. Strangers gathered. Kings sent letters. The porch "
        "became a school. The school became Stoicism. Twenty-three centuries later "
        "you are still hearing about it. His shipwreck built more than his ships "
        "ever carried."),
    "quote_row": 7,
    "beat_cta": "Send this to the friend who lost something this year.",
    "topic_query": "man walking storm harbor",
    "caption_first_line": "The storm did him a favor.",
}

EXEMPLAR_DEBATE = {
    "beat_hook": "Your grind is the most expensive thing you own.",
    "beat_reframe": (
        "You wear the exhaustion like a badge. Booked every hour. Answered every "
        "ping. And you tell yourself it is temporary. Two thousand years ago Rome "
        "had men like you. Senators sprinting between banquets and battles, "
        "collecting titles like you collect tabs. One philosopher watched them "
        "run. He was busy too. Tutor to an emperor. Richest man in the city. "
        "Then he wrote something in a letter that stopped his friend cold. "
        "He said the busiest men he knew were the poorest. Not in coin. In hours "
        "they actually owned. They rented every minute to someone else's urgency. "
        "Until the day ran out and none of it was theirs. He started guarding his "
        "mornings like a miser. Refusing meetings. Saying no to Caesar's circle. "
        "The city called it arrogance. He called it the only wealth that counts."),
    "quote_row": 7,
    "beat_cta": "Agree or disagree: busy is just broke with better branding.",
    "topic_query": "man rushing city crowd",
    "caption_first_line": "Busy is not the flex you think.",
}
```

Prompt rewrite: replace the reframe instruction block in `_ROLE_DEFAULT` with the 6-phase formula (0-3s viewer-hook + OPEN LOOP / 3-10s stakes in second person / 10-25s story entry ending on a CLIFFHANGER / 25-40s escalation, no resolution words / 40-50s payoff where both loops close on the quote / CTA), the anti-rules ("Never open with the historical figure. Never resolve a loop before the payoff. The word 'lesson' is banned. The viewer's life is the story — the ancient is the twist."), and both exemplars rendered as "EXEMPLAR (weird mode):\n<hook>\n<reframe>\n<cta>" blocks built by f-string concatenation from the constants (so the test's `in _ROLE_DEFAULT` assertions hold). Keep {mode}/{material}/{pool} slots and all existing length/style rules. NOTE: exemplar text contains no braces (verify) so .format stays safe.

Gate wiring in `write_story` (both drafts + retry validation):

```python
                ok, reason = validate_story(d or {}, mode=mode)
                if ok and mode != "punch":
                    ok, reason = validate_formula(d or {})
```

(and same pairing at the corrective-retry validation).

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest tests/test_viral_formula.py tests/test_content_brains.py tests/test_punch_arc.py -q` → all pass. Existing content-brain fixtures (Seneca long_reframe etc.) only feed `validate_story`, not `validate_formula` — unaffected. Full suite green.

- [ ] **Step 5: Commit**

```bash
git add studio/story_writer.py tests/test_viral_formula.py
git commit -m "feat(script): 6-phase viral formula — validator, exemplars, prompt rewrite (spec 1+2)"
```

### Task 2: Capsule pool → ≥60, keyed

**Files:**
- Modify: `src/content/weird_stories.py` (add `key` to all existing capsules + hypotheticals; append new capsules; if file exceeds 500 lines, move `WEIRD_CAPSULES` list to new `src/content/weird_capsules_data.py` and import)
- Test: `tests/test_capsule_pool.py`

**Interfaces:**
- Consumes: existing capsule schema {hook_fact, escalation, source_note, lesson_theme, send_cta} (+ hypothetical: True on that pool).
- Produces: every capsule + hypothetical dict gains `"key": "<slug>"` (unique across both pools, kebab-case, e.g. "zeno-shipwreck"); `len(WEIRD_CAPSULES) >= 54` and `len(WEIRD_CAPSULES) + len(WEIRD_HYPOTHETICALS) >= 60`.

**Content brief for the new capsules (write full capsules for each, attested, with the ancient source in source_note):** Diogenes captured by pirates & sold as a slave, "sell me to that man, he needs a master" (Diogenes Laertius VI); Epictetus' lame leg — "you will break it" told to his master (Origen/Celsus; Epictetus Discourses); Zeno's shipwreck → bookshop → Stoa Poikile (Diogenes Laertius VII); Cleanthes carried water by night to study by day (DL VII); Hipparchia refusing every suitor for Crates, "my dowry is philosophy" (DL VI); Crates the "door-opener" who walked into homes uninvited to counsel (DL VI); Chrysippus reportedly died laughing at his own joke about a donkey (DL VII); Socrates' 24-hour standing trance at Potidaea (Plato, Symposium); Socrates refusing to arrest Leon of Salamis under the Thirty (Plato, Apology); Cato marching on foot beside his soldiers, refusing a horse (Plutarch, Cato Minor); Cato refusing war spoils entirely (Plutarch); Musonius Rufus teaching ON the prison island Gyaros (Philostratus/fragments); Seneca's daily poverty rehearsal (Letters 18); Seneca's shipboard seasickness essay — the philosopher who couldn't stoic through nausea (Letters 53); Diogenes rolling his barrel uphill and down during war prep "to seem busy like everyone else" (Lucian); Diogenes asking Alexander to step out of his sunlight (Plutarch, Alexander); Diogenes' lamp in daylight "looking for a human" (DL VI); Diogenes eating in the marketplace where eating was shameful (DL VI); Antisthenes tearing his cloak to show vanity through the holes — Socrates: "I see your vanity through the holes" (DL VI); Pythagoras' bean taboo & the field where he stopped (DL VIII); Heraclitus playing dice with children instead of politics (DL IX); Anaxagoras on his son's death: "I knew I had begotten a mortal" (DL II); Aristippus and the shipwreck: "wealth that swims ashore with you" (Vitruvius VI pref.); Epicurus' bread-and-water feasts, "send me a pot of cheese" (DL X); Marcus Aurelius selling palace furniture to fund the war instead of taxing (Historia Augusta); Marcus writing "get up and do the work of a human being" to himself at dawn (Meditations 5.1); Epictetus on the stolen iron lamp — "he paid for it: a lamp for his honesty" (Discourses I.29); Zeno taxing himself with silence: two ears one mouth (DL VII); Cato practicing public failure by wearing unfashionable colors on purpose (Plutarch); Socrates dancing alone at dawn as exercise (Xenophon, Symposium); Thales falling into the well while studying stars, mocked by a servant girl (Plato, Theaetetus); Thales cornering the olive-press market to prove philosophers could be rich if they cared (Aristotle, Politics); Bias of Priene leaving the burning city empty-handed: "I carry everything I own" (Cicero, Paradoxa); Stilpo after the sack of Megara: "I lost nothing of my own" (Seneca, Constancy). That is 34 subjects — write at least 28 of them to reach ≥54 true capsules (26 existing incl. any you keep verbatim).

- [ ] **Step 1: Failing test**

```python
# tests/test_capsule_pool.py
"""60-capsule pool: keyed, attested, safe (spec 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.weird_stories import WEIRD_CAPSULES, WEIRD_HYPOTHETICALS
from src.content.trend_sources import is_unsafe
from src.content.safety_guards import mentions_named_person


def test_pool_size():
    assert len(WEIRD_CAPSULES) >= 54
    assert len(WEIRD_CAPSULES) + len(WEIRD_HYPOTHETICALS) >= 60


def test_every_capsule_keyed_and_complete():
    seen = set()
    for c in WEIRD_CAPSULES + WEIRD_HYPOTHETICALS:
        assert c.get("key") and c["key"] not in seen, c.get("key")
        seen.add(c["key"])
    for c in WEIRD_CAPSULES:
        for f in ("hook_fact", "escalation", "source_note", "lesson_theme", "send_cta"):
            assert c.get(f), (c["key"], f)
        assert "Send this" in c["send_cta"], c["key"]


def test_every_capsule_safe():
    for c in WEIRD_CAPSULES:
        joined = " ".join([c["hook_fact"], c["escalation"], c["send_cta"]])
        assert not is_unsafe(joined), c["key"]
        assert not mentions_named_person(joined), c["key"]
```

- [ ] **Step 2: Run** — FAIL (no `key` on existing capsules; pool too small).
- [ ] **Step 3: Implement** — add keys to all existing entries; write the new capsules per the content brief (each 2-4 sentences of hook_fact/escalation, real attested facts, source named). If any capsule trips `mentions_named_person`, extend `ALLOWED_FIGURES` in `src/content/safety_guards.py` with the ancient name (that's its purpose) and include that file in the commit.
- [ ] **Step 4: Run** — 3 passed; full suite green (pick_weird rotation tests unaffected — pool only grew).
- [ ] **Step 5: Commit**

```bash
git add src/content/weird_stories.py tests/test_capsule_pool.py
git commit -m "feat(content): 60-capsule attested pool with unique keys (spec 3)"
```

(Include `src/content/weird_capsules_data.py` and/or `src/content/safety_guards.py` if created/touched.)

### Task 3: Exclusion-aware pickers

**Files:**
- Modify: `src/content/weird_stories.py` (`pick_weird`), `src/content/debate_topics.py` (add `key` slugs to DEBATE_TOPICS + `pick_debate`)
- Test: `tests/test_material_exclusion.py`

**Interfaces:**
- Consumes: keyed pools (Task 2 for capsules; this task adds `key` to each DEBATE_TOPICS dict — slug from the topic, e.g. "hustle-culture").
- Produces: `pick_weird(row_number, exclude=frozenset()) -> dict` and `pick_debate(row_number, exclude=frozenset()) -> dict` — same deterministic base index; when the base pick's key is in `exclude`, advance to the next index (wrapping) until a non-excluded key; if ALL keys excluded, return the base pick (LRU semantics degrade gracefully to "least recently avoidable"); never None.

- [ ] **Step 1: Failing test**

```python
# tests/test_material_exclusion.py
"""Repetition kill: pickers skip recently-used material (spec 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.weird_stories import pick_weird, WEIRD_CAPSULES
from src.content.debate_topics import pick_debate, DEBATE_TOPICS


def test_excluded_key_skipped():
    base = pick_weird(0)
    nxt = pick_weird(0, exclude={base["key"]})
    assert nxt["key"] != base["key"]


def test_deterministic_with_same_exclude():
    ex = {WEIRD_CAPSULES[0]["key"], WEIRD_CAPSULES[1]["key"]}
    assert pick_weird(4, exclude=ex)["key"] == pick_weird(4, exclude=ex)["key"]


def test_all_excluded_still_returns():
    ex = {c["key"] for c in WEIRD_CAPSULES}
    assert pick_weird(0, exclude=ex) is not None


def test_debate_topics_keyed_and_excludable():
    keys = [t["key"] for t in DEBATE_TOPICS]
    assert len(keys) == len(set(keys)) and all(keys)
    base = pick_debate(2)
    assert pick_debate(2, exclude={base["key"]})["key"] != base["key"]
```

- [ ] **Step 2: Run** — FAIL (unexpected keyword `exclude` / missing `key`).
- [ ] **Step 3: Implement** — in `pick_weird`, keep the existing hypothetical/capsule index math for the BASE index, then:

```python
def pick_weird(row_number: int | None, exclude: frozenset = frozenset()) -> dict:
    """Deterministic weird pick; skips recently-used keys (spec 3)."""
    n = row_number or 0
    if n % 4 == 3:
        pool = WEIRD_HYPOTHETICALS
        base = (n // 4) % len(pool)
    else:
        pool = WEIRD_CAPSULES
        base = (n - n // 4) % len(pool)
    for step in range(len(pool)):
        cand = pool[(base + step) % len(pool)]
        if cand.get("key") not in exclude:
            return cand
    return pool[base]
```

Mirror in `pick_debate` (its existing index math + the same skip loop). Add `"key"` slugs to every DEBATE_TOPICS entry (kebab-case from the topic phrase, unique).

- [ ] **Step 4: Run** — 4 passed; `tests/test_content_brains.py` still green (positional calls unaffected). Full suite green.
- [ ] **Step 5: Commit**

```bash
git add src/content/weird_stories.py src/content/debate_topics.py tests/test_material_exclusion.py
git commit -m "feat(content): exclusion-aware material pickers with keyed debate topics (spec 3)"
```

### Task 4: material_key tracking end-to-end

**Files:**
- Modify: `src/core/data_store.py` (migration + `record_material` + `recent_material_keys`), `pipeline.py` (`_build_story_beats` exclude + stamp; `record_material` call at line ~1183 beside `record_arc`)
- Test: `tests/test_material_tracking.py`

**Interfaces:**
- Consumes: pickers with `exclude` (Task 3); pipeline `_build_story_beats` (material selection block) and the post-publish block calling `record_arc(post_row_id, quote_data.get("arc"))` at pipeline.py:1183.
- Produces: `data_store.record_material(row_id: int, key: str | None) -> None` (no-op on None, mirrors record_arc's style); `data_store.recent_material_keys(limit: int = 20) -> set[str]`; `posts.material_key` column added in `init_db` via `ALTER TABLE` guarded by try/except (additive, existing DBs migrate on next init). `_build_story_beats` sets `story["material_key"]` = capsule key / debate key / f"trend:{hash(quote_data['trend_topic']) & 0xffffffff:08x}" and passes `exclude=recent_material_keys()` (best-effort try/except → frozenset()) to pickers. `_run_pov_reel` copies `story.get("material_key")` into `quote_data["material_key"]`; the publish block calls `record_material(post_row_id, quote_data.get("material_key"))`.

- [ ] **Step 1: Failing test**

```python
# tests/test_material_tracking.py
"""material_key: recorded per post, feeds the exclusion window (spec 3)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import data_store


def _use_tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db, raising=False)
    # data_store resolves its path internally — check the module's actual
    # path constant name and patch THAT (read the module first).
    data_store.init_db()
    return db


def test_migration_and_roundtrip(tmp_path, monkeypatch):
    db = _use_tmp_db(tmp_path, monkeypatch)
    con = sqlite3.connect(db)
    con.execute("INSERT INTO posts (id, dry_run) VALUES (1, 0)")
    con.commit(); con.close()
    data_store.record_material(1, "zeno-shipwreck")
    data_store.record_material(1, None)          # no-op, never raises
    keys = data_store.recent_material_keys(limit=20)
    assert "zeno-shipwreck" in keys


def test_recent_limits_to_last_n(tmp_path, monkeypatch):
    db = _use_tmp_db(tmp_path, monkeypatch)
    con = sqlite3.connect(db)
    for i in range(30):
        con.execute("INSERT INTO posts (id, dry_run, material_key) "
                    "VALUES (?, 0, ?)", (i + 1, f"k{i}"))
    con.commit(); con.close()
    keys = data_store.recent_material_keys(limit=20)
    assert len(keys) == 20 and "k29" in keys and "k5" not in keys
```

NOTE: read `data_store.py` first — the posts schema (id column name, NOT NULL columns) and the DB-path constant differ from this sketch; adapt INSERTs and the monkeypatch target to reality, keeping the assertions' intent.

- [ ] **Step 2: Run** — FAIL AttributeError.
- [ ] **Step 3: Implement** — in `init_db` after the CREATE TABLE block:

```python
        try:
            conn.execute("ALTER TABLE posts ADD COLUMN material_key TEXT")
        except sqlite3.OperationalError:
            pass  # column exists
```

`record_material` mirrors `record_arc` (same connection helper, UPDATE posts SET material_key=? WHERE id=?, no-op when key falsy). `recent_material_keys` selects the last N non-null keys ordered by rowid/posted_at DESC into a set. Pipeline: in `_build_story_beats`, before picking material:

```python
        try:
            from src.core.data_store import recent_material_keys
            exclude = frozenset(recent_material_keys(20))
        except Exception:  # noqa: BLE001
            exclude = frozenset()
```

pass `exclude=exclude` to `pick_weird`/`pick_debate`; stamp `story["material_key"]` (capsule/topic `.get("key")`, or the trend hash for trend mode). In `_run_pov_reel`, after the story-beat mapping: `quote_data["material_key"] = story.get("material_key")`. At pipeline.py:1183 add `record_material(post_row_id, quote_data.get("material_key"))` (import beside record_arc at line 28).

- [ ] **Step 4: Run** — targeted + `tests/test_viral_arcs.py` + full suite green.
- [ ] **Step 5: Commit**

```bash
git add src/core/data_store.py pipeline.py tests/test_material_tracking.py
git commit -m "feat(content): material_key tracking — last-20 exclusion end-to-end (spec 3)"
```

### Task 5: Verification gate

- [ ] Full suite green; `git pull --rebase --autostash && git push`.
- [ ] Script quality check (no render needed): run `pipeline._build_story_beats(Config(), "weird", {...row 42...})` live once; print the script; verify by inspection: hook addresses viewer + plants loop; cliffhanger present; payoff at the end; NOT the Cato capsule if it's in the recent-20 (verify exclusion worked by checking the picked key differs from the last 20 recorded).
- [ ] One dry-run render (detached) for end-to-end sanity; then live acceptance at next open slot with Graph read-back.
- [ ] Confirm optimizer champion re-seed picked up the new prompt: `prompt_store.get("prompt.story_writer.role", _ROLE_DEFAULT) == _ROLE_DEFAULT` after one `assets.iter_managed()` / registry pass.

## Self-Review (done)

- Spec coverage: 1→T1 (formula+exemplars+prompt), 2→T1 (validator), 3→T2+T3+T4, 4 (back-compat)→T1 punch skip + T4 NULL handling + champion re-seed check in T5, 5 (errors)→each task, 6 (testing)→per task + T5. No gaps.
- Placeholders: none — T2's capsule brief lists 34 concrete attested subjects with sources (content-authoring is the task's work; acceptance is test-enforced).
- Type consistency: `validate_formula(d) -> (bool, str)` T1 only; `pick_weird/pick_debate(row, exclude=frozenset())` T3=T4 callers; `record_material(row_id, key)`/`recent_material_keys(limit)` T4 both sides; `key` field name uniform across pools and tracking.
