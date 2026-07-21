# Script Writer v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage the script writer: rubric subscores drive a conditional revision call, the writer chooses from a real 15–20 quote pool, an 8-angle hook-specialist pass replaces the hook, and top-performing real scripts feed back into the prompt context.

**Architecture:** `rubric.score_story_detailed` decomposes the existing scalar into 4 subscores + weakness strings; `write_story` adds a conditional revision stage (never-worse) and a hook-specialist pass (sonnet, coded pick); `pipeline` builds a real quote pool and swaps quote_data to the chosen row; scripts persist per post in a new `posts.script_json` column and `performance_digest.winning_scripts` injects top real scripts via extra_context.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), pytest, sqlite additive migration, Anthropic API via studio client.

## Global Constraints

- Revision trigger: any subscore ≤ 4 OR total < `REVISION_THRESHOLD`; ONE revision call max; revised ships only if it passes ALL gates AND its total ≥ pre-revision total (never-worse) (spec 3).
- Hook pass: sonnet role `hook_specialist` — register in BOTH `ROLE_MODELS` ("claude-sonnet-4-6") AND `ROLE_EFFORT` ("medium") in `studio/settings.py` (the settings-registration gotcha).
- Quote pool: ≤20 unposted rows, today's row FIRST; any failure → single today's-row pool (current behavior); chosen row swaps into quote_data (quote, attribution, row_number) so the CHOSEN row is marked posted (spec 2).
- Winner learning: reach ≥ 100, requires ≥3 scored scripts else []; static exemplars stay in-prompt; winners append to extra_context only (spec 5).
- Never-crash: every new stage best-effort with the prior stage's output as fallback.
- Spec refinement (approved direction): scripts persist in a NEW `posts.script_json` column via `record_script(row_id, script)` (mirrors `record_material`), NOT overloaded into `opt_versions_json` (that column is optimizer attribution).
- `data/pipeline.db` NOT tracked — never `git add` it. Tests: `.venv/bin/python -m pytest`. Files <500 lines.

## File Map

| File | Responsibility |
|---|---|
| `studio/rubric.py` (mod) | `score_story_detailed`, `score_hook`; `score_story` delegates |
| `studio/hook_specialist.py` (new) | `generate_hooks`, `pick_hook` |
| `studio/story_writer.py` (mod) | revision stage + hook-pass wiring in `write_story` |
| `studio/settings.py` (mod) | `hook_specialist` role rows |
| `pipeline.py` (mod) | `_quote_pool`, pool passing, chosen-row swap, `record_script` call |
| `src/core/data_store.py` (mod) | `script_json` migration, `record_script` |
| `src/analytics/performance_digest.py` (mod) | `winning_scripts(n=2)` |

---

### Task 1: Rubric subscores + score_hook

**Files:**
- Modify: `studio/rubric.py`
- Test: `tests/test_rubric_detailed.py`

**Interfaces:**
- Consumes: existing `_words`, `_ABSTRACTIONS`, `_CONCRETE_HINTS`, `_SPECIFIC_CTA`, `_sentence_lengths` internals.
- Produces: `score_story_detailed(d: dict) -> dict` with keys `hook`/`escalation`/`cta`/`simplicity` (each float 0–10), `total` (float), `weaknesses` (list[str], one entry per subscore ≤ 4, fixed strings below); `score_hook(hook: str) -> float` (higher better, ≥0, never raises). `score_story(d)` MUST keep its relative ordering (refactor to return `score_story_detailed(d)["total"]` scaled, or keep both consistent — existing rubric tests must stay green unchanged).

**Weakness strings (exact):** hook → "hook lacks a concrete image or number"; escalation → "escalation sentences run long — cut them shorter"; cta → "cta names no specific friend-type"; simplicity → "too many long words".

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric_detailed.py
"""Subscores power the revision stage; score_hook powers the hook pass."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.rubric import score_story_detailed, score_hook, score_story


def _story(hook, reframe, cta):
    return {"beat_hook": hook, "beat_reframe": reframe, "beat_cta": cta}


STRONG = _story("He ate stale bread on a marble floor for 3 days.",
                "Short. Sharp. It got worse. Then worse again. Nobody laughed.",
                "Send this to the friend who guards their stuff.")
WEAK_HOOK = _story("Success is really about mindset and growth.",
                   "Short. Sharp. It got worse. Then worse again. Nobody laughed.",
                   "Send this to the friend who guards their stuff.")


def test_subscores_in_range_and_keys():
    d = score_story_detailed(STRONG)
    for k in ("hook", "escalation", "cta", "simplicity"):
        assert 0.0 <= d[k] <= 10.0, k
    assert isinstance(d["total"], float) and isinstance(d["weaknesses"], list)


def test_weak_hook_gets_weakness_string():
    d = score_story_detailed(WEAK_HOOK)
    assert d["hook"] <= 4
    assert "hook lacks a concrete image or number" in d["weaknesses"]
    assert score_story_detailed(STRONG)["weaknesses"] == [] or \
        "hook lacks" not in " ".join(score_story_detailed(STRONG)["weaknesses"])


def test_total_orders_like_score_story():
    assert (score_story_detailed(STRONG)["total"] > score_story_detailed(WEAK_HOOK)["total"]) == \
           (score_story(STRONG) > score_story(WEAK_HOOK))


def test_garbage_never_raises():
    d = score_story_detailed({})
    assert d["total"] == 0.0 and d["weaknesses"] == []


def test_score_hook_ordering():
    concrete = "You checked your bank app 9 times before lunch."
    abstract = "Your mindset determines your success and growth."
    assert score_hook(concrete) > score_hook(abstract)
    assert score_hook("") >= 0.0
```

- [ ] **Step 2: Run** — `.venv/bin/python -m pytest tests/test_rubric_detailed.py -q` → FAIL ImportError.

- [ ] **Step 3: Implement** in `studio/rubric.py` (append; keep existing functions):

```python
_WEAKNESS = {
    "hook": "hook lacks a concrete image or number",
    "escalation": "escalation sentences run long — cut them shorter",
    "cta": "cta names no specific friend-type",
    "simplicity": "too many long words",
}


def _clamp10(x: float) -> float:
    return max(0.0, min(10.0, x))


def score_story_detailed(d: dict) -> dict:
    """Subscore decomposition of score_story's signals (spec 1). 0-10 each;
    weaknesses listed for any subscore <= 4. Never raises."""
    empty = {"hook": 0.0, "escalation": 0.0, "cta": 0.0, "simplicity": 0.0,
             "total": 0.0, "weaknesses": []}
    try:
        hook = d.get("beat_hook") or ""
        reframe = d.get("beat_reframe") or ""
        cta = d.get("beat_cta") or ""
        if not (hook and reframe and cta):
            return empty
        h = 5.0 + 2.0 * len(_CONCRETE_HINTS.findall(hook.lower())) \
            - 2.0 * sum(w.lower() in _ABSTRACTIONS for w in _words(hook)) \
            + (1.0 if not hook.rstrip().endswith("?") else -2.0)
        lens = _sentence_lengths(reframe)
        mean = sum(lens) / len(lens)
        e = 10.0 - max(0.0, (mean - 6.0)) * 1.2
        if _SPECIFIC_CTA.search(cta):
            c = 9.0
        elif "send" in cta.lower() or "agree" in cta.lower():
            c = 6.0
        else:
            c = 3.0
        all_words = _words(hook) + _words(reframe) + _words(cta)
        long_frac = (sum(len(w) > 8 for w in all_words) / len(all_words)) if all_words else 1.0
        s = 10.0 - 40.0 * long_frac
        subs = {"hook": _clamp10(h), "escalation": _clamp10(e),
                "cta": _clamp10(c), "simplicity": _clamp10(s)}
        weaknesses = [_WEAKNESS[k] for k in ("hook", "escalation", "cta", "simplicity")
                      if subs[k] <= 4.0]
        total = round(subs["hook"] * 0.4 + subs["escalation"] * 0.25
                      + subs["cta"] * 0.2 + subs["simplicity"] * 0.15, 4)
        return {**subs, "total": total, "weaknesses": weaknesses}
    except Exception:  # noqa: BLE001 - judge never crashes
        return empty


def score_hook(hook: str) -> float:
    """Hook-variant scoring for the specialist pass (spec 4)."""
    try:
        hl = (hook or "").lower()
        score = 5.0
        score += 2.0 * len(_CONCRETE_HINTS.findall(hl))
        score -= 2.0 * sum(w in _ABSTRACTIONS for w in _words(hl))
        if hook.rstrip().endswith("?"):
            score -= 3.0
        for phrase in ("that's why", "the answer", "here's how", "the lesson"):
            if phrase in hl:
                score -= 3.0
        return max(0.0, round(score, 4))
    except Exception:  # noqa: BLE001
        return 0.0
```

NOTE: if `test_total_orders_like_score_story` fails on the given pair, adjust the subscore constants minimally (not the tests) — ordering on this pair is the contract. Verify existing `tests/test_rubric.py` stays green untouched.

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest tests/test_rubric_detailed.py tests/test_rubric.py -q` → all pass; full suite green.

- [ ] **Step 5: Commit**

```bash
git add studio/rubric.py tests/test_rubric_detailed.py
git commit -m "feat(rubric): subscore decomposition + hook scoring (spec 1)"
```

### Task 2: Quote pool + chosen-row swap

**Files:**
- Modify: `pipeline.py` (`_quote_pool` helper; `_build_story_beats` pool + swap)
- Test: `tests/test_quote_pool.py`

**Interfaces:**
- Consumes: `studio.run._build_pool(excel_path)` (returns [{row_number, quote, audience}] for unposted rows — READ it; note it lacks attribution: extend the returned dicts here by reading the attribution column in the same loop OR default attribution "— Socrates" when absent; check the excel columns in `studio/run.py:_build_pool` and `src/core/excel_reader.py` first).
- Produces: `pipeline._quote_pool(quote_data) -> list[dict]` (`{row_number, quote, attribution}`, today's row FIRST, ≤20, failure → `[today's row]`); `_build_story_beats` passes this pool to `write_story` and, on success, when `story["quote_row"] != quote_data["row_number"]`: sets `quote_data["quote"]`, `quote_data["attribution"]` (if present in pool entry), `quote_data["row_number"]` to the chosen entry's values.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quote_pool.py
"""The writer picks the quote; the chosen row becomes the consumed row (spec 2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_quote_pool_today_first_and_capped(monkeypatch):
    rows = [{"row_number": i, "quote": f"q{i}", "audience": "stuck"} for i in range(30)]
    monkeypatch.setattr("studio.run._build_pool", lambda p: rows)
    pool = pipeline._quote_pool({"row_number": 7, "quote": "q7"})
    assert pool[0]["row_number"] == 7
    assert len(pool) <= 20
    assert all("quote" in e and "row_number" in e for e in pool)


def test_quote_pool_failure_falls_back(monkeypatch):
    monkeypatch.setattr("studio.run._build_pool",
                        lambda p: (_ for _ in ()).throw(RuntimeError("no excel")))
    pool = pipeline._quote_pool({"row_number": 3, "quote": "today"})
    assert pool == [{"row_number": 3, "quote": "today",
                     "attribution": pool[0].get("attribution", "— Socrates")}] or \
           (len(pool) == 1 and pool[0]["row_number"] == 3)


def test_chosen_row_swaps_into_quote_data(monkeypatch):
    def fake_write_story(client, mode, material, pool, extra_context=""):
        return {"beat_hook": "You keep score of everything you could lose tomorrow night.",
                "beat_reframe": ("You count it quietly. " + "He kept walking. " * 60
                                 + "And nobody expected what he did next. "
                                 + "He kept walking. " * 10),
                "quote_row": 12, "beat_cta": "Send this to the friend who would start over.",
                "topic_query": "man storm", "caption_first_line": "He lost it all."}

    monkeypatch.setattr("studio.story_writer.write_story", fake_write_story)
    monkeypatch.setattr(pipeline, "_quote_pool", lambda qd: [
        {"row_number": 5, "quote": "today quote", "attribution": "— A"},
        {"row_number": 12, "quote": "chosen quote", "attribution": "— B"}])

    class _Cfg:
        ANTHROPIC_API_KEY = "k"

    qd = {"row_number": 5, "quote": "today quote", "audience": "stuck"}
    story = pipeline._build_story_beats(_Cfg(), "weird", qd)
    assert story is not None
    assert qd["row_number"] == 12 and qd["quote"] == "chosen quote"
    assert qd["attribution"] == "— B"
```

NOTE: the fake story must pass validate_story+validate_formula+leak gates? NO — write_story is monkeypatched wholesale here, gates live inside it; `_build_story_beats` only re-checks safety (is_unsafe/mentions_named_person) on the joined text — the fake text above is safe. Verify the reframe passes the safety guards (it does — no names, no denylist).

- [ ] **Step 2: Run** — FAIL (`AttributeError: _quote_pool`).

- [ ] **Step 3: Implement** in `pipeline.py`:

```python
def _quote_pool(quote_data: dict) -> list[dict]:
    """Real quote pool for the writer's earned-twist choice (spec 2): today's
    row first, then up to 19 more unposted rows. Failure -> single-row pool."""
    today = {"row_number": quote_data.get("row_number"),
             "quote": quote_data.get("quote", ""),
             "attribution": quote_data.get("attribution", "— Socrates")}
    try:
        from studio.run import _build_pool
        rows = _build_pool(str(EXCEL_PATH))
        pool = [today]
        for r in rows:
            if r["row_number"] == today["row_number"]:
                continue
            pool.append({"row_number": r["row_number"], "quote": r["quote"],
                         "attribution": r.get("attribution", "— Socrates")})
            if len(pool) >= 20:
                break
        return pool
    except Exception:  # noqa: BLE001 - pool is an upgrade, not a dependency
        return [today]
```

In `_build_story_beats`: replace the single-quote pool construction with `pool = _quote_pool(quote_data)`; after the story passes safety checks and material stamping, add:

```python
        chosen = next((p for p in pool
                       if p["row_number"] == story.get("quote_row")), None)
        if chosen and chosen["row_number"] != quote_data.get("row_number"):
            quote_data["quote"] = chosen["quote"]
            quote_data["attribution"] = chosen.get("attribution", "— Socrates")
            quote_data["row_number"] = chosen["row_number"]
```

Check `studio/run.py:_build_pool` for an attribution column — if the excel row carries one (look at `excel_reader` column mapping), include it in `_build_pool`'s dicts (add the field there, additive) or read it here; otherwise the "— Socrates" default stands.

- [ ] **Step 4: Run** — targeted + `tests/test_viral_arcs.py` + `tests/test_material_tracking.py` + full suite → green.

- [ ] **Step 5: Commit**

```bash
git add pipeline.py tests/test_quote_pool.py
git commit -m "feat(script): real quote pool — the writer picks the earned twist (spec 2)"
```

(Include `studio/run.py` if attribution was added there.)

### Task 3: Conditional revision stage

**Files:**
- Modify: `studio/story_writer.py`
- Test: `tests/test_revision_stage.py`

**Interfaces:**
- Consumes: `rubric.score_story_detailed` (Task 1); existing gates (`validate_story`, `validate_formula`, `_quote_leak`, pool-membership) inside `write_story`.
- Produces: constant `REVISION_THRESHOLD = 6.5`; after the rubric picks the 2-draft winner, when `detail["weaknesses"]` non-empty OR `detail["total"] < REVISION_THRESHOLD`: ONE revision call (same role prompt; user message = subscore report + weaknesses + "Rewrite the four beats fixing EXACTLY the named weaknesses. Keep every phrase that already works." + `json.dumps(winner)`), revised must pass ALL gates AND `score_story_detailed(revised)["total"] >= detail["total"]` else winner ships.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_revision_stage.py
"""Conditional revision: subscore report in, never-worse out (spec 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.story_writer import write_story, REVISION_THRESHOLD

POOL = [{"row_number": 1, "quote": "He who has a why can bear any how."}]

WEAK = {"beat_hook": "Your mindset shapes your success and growth every day.",
        "beat_reframe": ("You tell yourself tomorrow. " + "He kept walking. " * 55
                         + "And nobody expected what he did next. "
                         + "He kept going anyway. " * 12),
        "quote_row": 1, "beat_cta": "Share this post.",
        "topic_query": "man storm", "caption_first_line": "Read it again."}

STRONG_REVISION = dict(WEAK,
    beat_hook="You checked your bank app 9 times before lunch today.",
    beat_cta="Send this to the friend who counts everything twice.")


def test_revision_fires_and_ships_better(monkeypatch):
    calls = []

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            if len(calls) <= 2:
                return dict(WEAK)
            return dict(STRONG_REVISION)

    out = write_story(C(), "weird", {"hook_fact": "x"}, POOL)
    assert out is not None and out["beat_hook"].startswith("You checked")
    assert len(calls) == 3                       # 2 drafts + 1 revision
    assert "fixing EXACTLY" in calls[2] or "weakness" in calls[2].lower()


def test_revision_never_worse(monkeypatch):
    calls = []
    WORSE = dict(WEAK, beat_cta="Share.")        # even weaker cta

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            return dict(WEAK) if len(calls) <= 2 else dict(WORSE)

    out = write_story(C(), "weird", {"hook_fact": "x"}, POOL)
    assert out is not None and out["beat_cta"] == "Share this post."  # original kept


def test_strong_draft_skips_revision(monkeypatch):
    calls = []
    STRONG = dict(WEAK,
        beat_hook="You counted your savings 3 times on a marble-cold night.",
        beat_cta="Send this to the friend who guards their stuff.")

    class C:
        def call(self, role, prefix, role_system, user, schema):
            calls.append(user)
            return dict(STRONG)

    out = write_story(C(), "weird", {"hook_fact": "x"}, POOL)
    assert out is not None and len(calls) == 2   # no revision call
```

NOTE: verify the WEAK fixture actually passes validate_story (word budget 140–215 total — count the repeated strings; adjust repeat counts so total lands in-range) AND validate_formula (has "You" early, cliffhanger marker present) AND that its detailed total is below REVISION_THRESHOLD while STRONG's is above; tune fixture words if needed (tests are the contract, fixtures may be tuned).

- [ ] **Step 2: Run** — FAIL ImportError (REVISION_THRESHOLD).

- [ ] **Step 3: Implement** — in `write_story`, after `valid.sort(...)` / winner selection:

```python
        if valid:
            valid.sort(key=lambda t: t[0], reverse=True)
            winner = valid[0][1]
            winner = _maybe_revise(client, role, winner, mode, pool, ctx)
            return winner
```

New module-level constant + helper (helper defined inside the module, using the same gates):

```python
REVISION_THRESHOLD = 6.5


def _passes_all_gates(d, mode, pool):
    ok, _ = validate_story(d or {}, mode=mode)
    if ok and mode != "punch":
        ok, _ = validate_formula(d or {})
    if ok and d and not any(p["row_number"] == d.get("quote_row") for p in pool):
        ok = False
    return ok
```

`_maybe_revise(client, role, winner, mode, pool, ctx)`: compute `detail = score_story_detailed(winner)`; if no weaknesses and total ≥ threshold → return winner; else build the report user message (per-subscore lines + weaknesses + the exact instruction + `json.dumps(winner)`), one `client.call`, run `_passes_all_gates` + the `_quote_leak` check (note: `_quote_leak` is currently a closure inside write_story — REFACTOR it to a module-level `_quote_leak(d, pool)` so both call sites share it; update existing call sites), and the never-worse total comparison; return revised or winner. Whole helper try/except → winner.

- [ ] **Step 4: Run** — targeted + `tests/test_viral_formula.py` + full suite → green.

- [ ] **Step 5: Commit**

```bash
git add studio/story_writer.py tests/test_revision_stage.py
git commit -m "feat(script): conditional revision stage — subscore report in, never-worse out (spec 3)"
```

### Task 4: Hook specialist

**Files:**
- Create: `studio/hook_specialist.py`
- Modify: `studio/story_writer.py` (wiring), `studio/settings.py` (role rows)
- Test: `tests/test_hook_specialist.py`

**Interfaces:**
- Consumes: `rubric.score_hook` (Task 1); `types._obj` for the schema; validate_formula's viewer-token set (duplicate the small check locally — do not import private internals).
- Produces: `HOOK_ANGLES` (8-tuple: "fear", "curiosity", "status", "absurdity", "loss", "time-urgency", "secret", "challenge"); `generate_hooks(client, story: dict, n=8) -> list[str]` (schema `{"hooks": [str]}`, one per angle, [] on failure); `pick_hook(candidates: list[str], fallback: str) -> str` (validates: contains a viewer token you/your/you're/you've/you'll/you'd/yourself via `re.findall(r"[a-z']+")`, ≤15 words, not ending "?", no resolution phrase; scores survivors with `score_hook`; max or fallback). `write_story` wiring: after the final story passes all gates (post-revision), `story["beat_hook"] = pick_hook(generate_hooks(client, story), story["beat_hook"])` inside try/except. Settings: `"hook_specialist": "claude-sonnet-4-6"` in ROLE_MODELS AND `"hook_specialist": "medium"` in ROLE_EFFORT.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hook_specialist.py
"""8-angle hook pass: coded validation + scoring, fallback-safe (spec 4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.hook_specialist import HOOK_ANGLES, generate_hooks, pick_hook


def test_eight_angles():
    assert len(HOOK_ANGLES) == 8 and len(set(HOOK_ANGLES)) == 8


def test_generate_hooks_calls_role(monkeypatch):
    class C:
        def call(self, role, prefix, role_system, user, schema):
            assert role == "hook_specialist"
            return {"hooks": [f"You feel angle {a} tonight." for a in HOOK_ANGLES]}
    hooks = generate_hooks(C(), {"beat_reframe": "story text", "beat_hook": "old"})
    assert len(hooks) == 8


def test_generate_hooks_failure_returns_empty():
    class Dead:
        def call(self, *a, **k):
            raise RuntimeError("api down")
    assert generate_hooks(Dead(), {}) == []


def test_pick_hook_validates_and_scores():
    cands = [
        "The lesson is that success comes from mindset.",   # no viewer + resolution
        "Why do you keep doing this?",                       # question
        "You checked your bank app 9 times before lunch.",   # concrete winner
        "Your mindset determines your growth and success.",  # abstract
    ]
    assert pick_hook(cands, "fallback you keep.") == \
        "You checked your bank app 9 times before lunch."


def test_pick_hook_all_invalid_falls_back():
    assert pick_hook(["No viewer here at all."], "You still matter tonight.") == \
        "You still matter tonight."
```

- [ ] **Step 2: Run** — FAIL ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# studio/hook_specialist.py
"""8-angle hook variant pass (spec 4). Hooks decide retention; the writer's
single hook attempt becomes 8 psychological angles with a coded judge."""
import re

from studio.types import _obj
from studio.rubric import score_hook

HOOK_ANGLES = ("fear", "curiosity", "status", "absurdity", "loss",
               "time-urgency", "secret", "challenge")

_HOOKS_SCHEMA = _obj({"hooks": {"type": "array", "items": {"type": "string"}}},
                     ["hooks"])
_VIEWER = {"you", "your", "you're", "you've", "you'll", "you'd", "yourself"}
_RESOLUTION = ("that's why", "the answer", "here's how", "the lesson")

_PREFIX = (
    "You write scroll-stopping first lines for 60-second Stoic story reels. "
    "A hook is ONE statement, <=15 words, addressed to the viewer (you/your), "
    "opening a loop it never resolves.")


def generate_hooks(client, story: dict, n: int = 8) -> list[str]:
    """One call, one hook per angle. [] on any failure (never raises)."""
    try:
        role = (
            "The finished story:\n"
            f"{story.get('beat_reframe', '')}\n\n"
            f"Current hook: {story.get('beat_hook', '')}\n\n"
            "Write EXACTLY one hook per angle, in this order: "
            + ", ".join(HOOK_ANGLES[:n]) + ". Each <=15 words, a STATEMENT, "
            "second person, planting a mystery the story pays off. Output JSON.")
        d = client.call("hook_specialist", _PREFIX, role,
                        "Write the hooks now.", _HOOKS_SCHEMA)
        hooks = [h for h in (d or {}).get("hooks", []) if isinstance(h, str)]
        return hooks[:n]
    except Exception:  # noqa: BLE001 - the story's own hook is the fallback
        return []


def _valid(hook: str) -> bool:
    hl = hook.lower()
    toks = set(re.findall(r"[a-z']+", hl))
    if not (toks & _VIEWER):
        return False
    if len(hook.split()) > 15 or hook.rstrip().endswith("?"):
        return False
    return not any(p in hl for p in _RESOLUTION)


def pick_hook(candidates: list[str], fallback: str) -> str:
    """Best valid candidate by score_hook, else the fallback."""
    try:
        valid = [c for c in candidates if c and _valid(c)]
        if not valid:
            return fallback
        return max(valid, key=score_hook)
    except Exception:  # noqa: BLE001
        return fallback
```

Settings rows; wiring in `write_story` right before each successful `return` of a story (post-revision winner AND the corrective-retry success path):

```python
            try:
                from studio.hook_specialist import generate_hooks, pick_hook
                if mode != "punch":
                    winner["beat_hook"] = pick_hook(
                        generate_hooks(client, winner), winner["beat_hook"])
            except Exception:  # noqa: BLE001
                pass
```

(the replaced hook must still satisfy downstream consumers — it passes the same viewer/statement constraints validate_formula checks, by `_valid`'s construction).

- [ ] **Step 4: Run** — targeted + `tests/test_revision_stage.py` (its call-count assertions: hook pass adds ONE call per successful story — update those counts, e.g. 3 → 4 and 2 → 3, keeping their intent) + full suite → green.

- [ ] **Step 5: Commit**

```bash
git add studio/hook_specialist.py studio/story_writer.py studio/settings.py tests/test_hook_specialist.py tests/test_revision_stage.py
git commit -m "feat(script): 8-angle hook specialist pass with coded pick (spec 4)"
```

### Task 5: Winner learning + gate

**Files:**
- Modify: `src/core/data_store.py` (script_json migration + `record_script`), `pipeline.py` (persist call + winners injection), `src/analytics/performance_digest.py` (`winning_scripts`)
- Test: `tests/test_winner_learning.py`

**Interfaces:**
- Consumes: `record_material` pattern (mirror exactly); digest DB access pattern; `_build_story_beats` extra_context assembly.
- Produces: `data_store.record_script(row_id: int, script: dict | None) -> None` (JSON into new `posts.script_json` column, additive ALTER migration in init_db, falsy → no-op); `performance_digest.winning_scripts(n=2, db_path=DEFAULT_DB) -> list[dict]` (`{"hook", "reframe", "cta", "sends_per_reach"}`, posts with non-null script_json × post_metrics, reach ≥ 100, ranked desc, `[]` when fewer than 3 scored scripts); pipeline: publish block calls `record_script(post_row_id, quote_data.get("script"))` — `_run_pov_reel` sets `quote_data["script"] = {"hook": ..., "reframe": ..., "cta": ...}` when a story arc shipped; `_build_story_beats` appends the winners block to extra_context: `"REAL WINNERS FROM THIS ACCOUNT (study what worked):"` + per winner hook/first-60-words-of-reframe/cta (best-effort try/except).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_winner_learning.py
"""The writer studies its own hits once >=3 scripts have sends data (spec 5)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import data_store
from src.analytics.performance_digest import winning_scripts


def _seed(db_path, n_scored):
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, "
                "post_id TEXT, dry_run INT, script_json TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS post_metrics (post_id TEXT PRIMARY KEY, "
                "shares INT, reach INT)")
    for i in range(n_scored):
        s = json.dumps({"hook": f"hook{i}", "reframe": "r " * 80, "cta": f"cta{i}"})
        con.execute("INSERT INTO posts (id, post_id, dry_run, script_json) "
                    "VALUES (?, ?, 0, ?)", (i + 1, f"p{i}", s))
        con.execute("INSERT INTO post_metrics VALUES (?, ?, 300)", (f"p{i}", i * 3))
    con.commit(); con.close()


def test_below_three_scored_returns_empty(tmp_path):
    db = tmp_path / "t.db"; _seed(db, 2)
    assert winning_scripts(db_path=db) == []


def test_top_two_by_sends(tmp_path):
    db = tmp_path / "t.db"; _seed(db, 5)
    w = winning_scripts(n=2, db_path=db)
    assert [x["hook"] for x in w] == ["hook4", "hook3"]
    assert all("sends_per_reach" in x for x in w)


def test_record_script_roundtrip(tmp_path, monkeypatch):
    # Adapt the monkeypatch target to data_store's real DB-path mechanism
    # (same approach tests/test_material_tracking.py used — read that file).
    pass  # replaced during implementation per the material-tracking pattern
```

Replace the third test's `pass` with the real pattern copied from `tests/test_material_tracking.py::test_migration_and_roundtrip` (same monkeypatch + insert + assert `script_json` readable via a direct SELECT after `record_script(1, {"hook": "h"})`).

- [ ] **Step 2: Run** — FAIL ImportError.
- [ ] **Step 3: Implement** — migration + record_script mirror `material_key`/`record_material` exactly (same guarded ALTER, same connection style). `winning_scripts`:

```python
def winning_scripts(n=2, db_path=DEFAULT_DB) -> list[dict]:
    """Top real scripts by sends-per-reach (spec 5). [] until >=3 scored."""
    import json as _json
    try:
        con = sqlite3.connect(str(db_path))
        try:
            rows = con.execute(
                "SELECT p.script_json, m.shares, m.reach FROM posts p "
                "JOIN post_metrics m ON p.post_id = m.post_id "
                "WHERE p.dry_run=0 AND p.script_json IS NOT NULL "
                "AND m.reach >= 100").fetchall()
        finally:
            con.close()
        scored = []
        for sj, shares, reach in rows:
            try:
                s = _json.loads(sj)
                scored.append({**{k: s.get(k, "") for k in ("hook", "reframe", "cta")},
                               "sends_per_reach": round((shares or 0) / reach, 4)})
            except Exception:  # noqa: BLE001
                continue
        if len(scored) < 3:
            return []
        scored.sort(key=lambda e: e["sends_per_reach"], reverse=True)
        return scored[:n]
    except Exception:  # noqa: BLE001 - learning is optional
        return []
```

Pipeline wiring: `_run_pov_reel` after story-beat mapping adds `quote_data["script"] = {"hook": hook_text, "reframe": story["beat_reframe"], "cta": cta_text}`; publish block `record_script(post_row_id, quote_data.get("script"))` beside record_material; `_build_story_beats` extra_context append:

```python
        try:
            from src.analytics.performance_digest import winning_scripts
            winners = winning_scripts(2)
            if winners:
                block = "\nREAL WINNERS FROM THIS ACCOUNT (study what worked):\n"
                for w in winners:
                    block += (f"- HOOK: {w['hook']}\n  STORY OPENING: "
                              f"{' '.join(w['reframe'].split()[:60])}\n  CTA: {w['cta']}\n")
                extra = (extra + block) if extra else block
        except Exception:  # noqa: BLE001
            pass
```

- [ ] **Step 4: Run** — targeted + full suite → green.
- [ ] **Step 5: Commit**

```bash
git add src/core/data_store.py pipeline.py src/analytics/performance_digest.py tests/test_winner_learning.py
git commit -m "feat(script): winner learning — real top scripts feed the writer (spec 5)"
```

### Task 6: Verification gate

- [ ] Full suite green; `git pull --rebase --autostash && git push`.
- [ ] Live generation check (no render): `_build_story_beats` for a weird row — print the script; verify: hook differs from draft hook only if the specialist won (log shows the pass); quote chosen from pool (print quote_row + swapped quote); subscore/revision behavior visible in output.
- [ ] Dry-run render (detached) end-to-end sanity; live acceptance at next open slot with Graph read-back.
- [ ] Cost sanity: count client calls in the live check (expect 3–4).

## Self-Review (done)

- Spec coverage: 1→T1, 2→T2, 3→T3, 4→T4, 5→T5, cost/error→each task + T6. Spec's record_post_versions mechanism refined to record_script (declared in Global Constraints). No gaps.
- Placeholders: T5 Step-1 third test intentionally directs copying the existing material-tracking pattern with exact assertions named — the pattern file exists in-repo; acceptable as a precise instruction, everything else is complete code.
- Type consistency: `score_story_detailed`/`score_hook` (T1) = T3/T4 consumers; `_passes_all_gates(d, mode, pool)` + module-level `_quote_leak(d, pool)` refactor (T3) used consistently; `winning_scripts(n, db_path)` (T5) matches injection call; `record_script(row_id, script)` mirrors record_material.
