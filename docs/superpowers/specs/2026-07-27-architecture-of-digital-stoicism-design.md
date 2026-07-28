---
name: architecture-of-digital-stoicism-design
description: Strategic prompt replacement (Digital Stoicism voice) + audio overhaul (baritone + emotion tags) + visual overhaul (Digital Monumentalism + Hopecore) + 6 remaining bug fixes.
date: 2026-07-27
status: PROPOSED
---

# Architecture of Digital Stoicism — Master Upgrade Design

Strategic prompt replacement, audio/visual overhaul, and 6 real bug fixes across the
Socrates Instagram automation pipeline.

## 1. Scope

### 1.1 Already in working tree (skip)

Verified via reading on 2026-07-27:

- `studio/types.py` `CREATIVE_BRIEF_SCHEMA["quote"]` already contains
  `row_number`/`text`/`author`/`source`/`need_new`/`theme`
- `pipeline.py` carousel wiring (`args.carousel`) is wired
- `src/visual/motion_effects.py` uses `Easing.EASE_OUT_EXPO` (enum-qualified)
- `src/core/data_store.py` `init_db()` already adds `posts.hook_id` migration (L81-82)
- `src/analytics/hook_tracker.py` reads `hook_id`, Thompson-sampling enabled
- `team/debate.py` + `team/orchestrator.py` raise `PlanNotApprovedError` when
  reviewer never approves
- `tests/test_phase1_integration.py` + `test_phase2_integration.py` use real assertions
- `src/content/script_01_assembler.py` already removed
- `socrates_pipeline/` already removed

### 1.2 Real bugs to fix

| # | File | Defect | Fix |
|---|------|--------|-----|
| 1 | `src/video/reel_composer.py` L278 | `MotionEngine.random_transition()` unconditionally overwrites beat-sync `transition_type` chosen at L217 | Guard: only assign random when beat_sync_info absent or transition_type None |
| 2 | `team/orchestrator.py` L132 | `dry_run` parameter accepted but never threaded to downstream stages → paid LLM calls + writes fire on dry run | Thread through every stage; gate `save_proposal`/`mark_posted`/Graph API/MetricsCollector; log "DRY-RUN: skipped X" |
| 3 | `config.py` | No validation that `META_ACCESS_TOKEN`/`META_APP_ID`/`META_APP_SECRET` form a coherent set | Add `_validate_meta_token_relationship()`: app_id+secret without token → RuntimeError; token without both → warning; all three set → verify token via Graph `/debug_token` |
| 4 | `src/audio/trending_audio.py` `FALLBACK_TRACKS` | Empty URL strings → silent fallthrough → broken local synth fallback | Replace with real validated Jamendo CDN URLs (HEAD-check 200); add local `assets/audio/fallback/*.mp3` (royalty-free) when Jamendo down |
| 5 | `src/analytics/competitor.py` L18 | `DB_PATH = Path(__file__).parent.parent / "data" / "pipeline.db"` resolves to `src/data/...` (file is in `src/analytics/`) | Use `parent.parent.parent` → repo-root `data/...`, matching `data_store.py` convention |
| 6 | `src/prompts/architect.py` L283-313 | Raw `httpx.Client.post(...)` to `api.anthropic.com` uses deprecated `claude-3-haiku-20240307`; bypasses official SDK | Migrate to `anthropic.Anthropic(api_key=...).messages.create(model="claude-haiku-4-5", ...)` |

### 1.3 Strategic upgrade scope

**Prompt replacement (4 agents, full replacement per user selection):**

- **Strategist** → Content Director & Chief Philosopher template
- **Copywriter** → Temporal Scripting Formula (Hook ≤12w / Dev staccato pivots every 8-10s / Close DM-share or debate CTA, NEVER generic follow)
- **Story Writer** → Historical Biographer template (3-mode: story / punch / weird preserved)
- **Prompt Architect** → Digital Monumentalism + Hopecore + Photorealism Rig overlays

**Audio upgrade:**

- Deep expressive male baritone voices: Josh (`TxGEqnHWrfWFTfWB9MjX`),
  Bill (`pqHfZ75CvOlQylNhV4`), David (`onwK4e9ZLuTAKqWW03F9`)
- ElevenLabs native emotion tags in copy: `[sighs] [dryly] [sarcastically] [emphatic] [calmly] [pause]`
- `[pause]` → `<break time="0.5s" />` (ElevenLabs renders as silence)
- New default REEL_VOICE = `bill` (deepest), epic_warrior opt-in `josh`

**Visual upgrade — Digital Monumentalism:**

- 4 mood pools: dark_philosophical / dramatic_ancient / stark_minimal / epic_warrior
- Composition, lighting, texture, atmosphere constants focused on weathered
  marble, Roman ruins, lone robed figure scale, low fog, firelight on stone
- Photorealism Rig always-on anchoring suffix

**Hopecore:**

- 3 mood pools: cinematic_hopeful / mystical_greek / calm_stoic
- Composition, lighting, texture, atmosphere focused on golden light, rain
  on windows, mist on cliffs, soft fabric, dawn

**Photorealism Rig (always-on suffix):**

```
photorealistic, shot on Phase One IQ4, 80mm prime lens,
35mm film grain, no obvious 3D render, no plastic surfaces,
natural color science, no over-saturated highlights
```

## 2. Architectural decisions

### 2.1 Sequencing: Bugs-first, prompts-last (Approach A)

Land all 6 bug fixes + SDK migration → prove green test baseline → drop prompt
replacements + audio/visual upgrades. Cleanest bisection. SDK swap is risk
surface; prompt changes are large diffs easier to review against a known-green
baseline.

### 2.2 Prompt rewrite mode: Full replacement

Replace role bodies + few-shot with supplied templates wholesale. Preserves
schema contracts (zero changes to `studio/types.py` schemas). Pipeline callers
need no edits — function signatures unchanged.

### 2.3 Schema stability

Zero changes to `CREATIVE_BRIEF_SCHEMA` / `CONCEPTS_SCHEMA` / `CONCEPT_SCHEMA`
/ `STORY_SCHEMA`. All four agents still emit JSON conforming to existing
schemas. Validators untouched.

### 2.4 Plumbing contracts preserved

- `studio/strategist.make_brief(client, perf, slot, recent_posts, pool, extra_context="")` unchanged
- `studio/copywriter.draft(client, perf, brief, extra_context="")` unchanged
- `studio/story_writer.write_story(client, mode, material, pool, extra_context="")` unchanged
- `PromptArchitect.build(...)` signature unchanged

### 2.5 Voice ID provenance

Josh/Bill/David IDs verified against the project's ElevenLabs account
(`/v1/voices` listing, 2026-07-19). Existing `sage`/`intense`/`contemplative`
aliases preserved as fallback for unchanged callers.

### 2.6 Photorealism Rig is non-negotiable

Always-on suffix regardless of mood/style — prevents FLUX generation drift
back into "obvious AI render" territory that triggers platform suppression.

## 3. Implementation plan

### Phase 1 — Bugs (Sections 1+2)

Step 1.1 — `src/video/reel_composer.py` transition preservation

```python
# Line 217 region: assign beat-sync choice
if beat_sync_info and beat_sync_info.get("transition_type"):
    transition_type = beat_sync_info["transition_type"]
# Line 278: only random-fallback when above failed
if transition_type is None:
    transition_type = MotionEngine.random_transition(seed=hash(timestamp) % 10000)
```

Step 1.2 — `team/orchestrator.py` dry_run threading

- Add `dry_run: bool` parameter to every stage's callable wrapper
- Gate: `if not dry_run: proposal.save(...)` / `mark_posted(...)` / `metrics.record(...)`
- Wrap StudioClient to no-op paid model calls when dry_run=True (cheap validation
  only)
- Log every skipped action: `"DRY-RUN: skipped proposal save for {date}/{slot}"`

Step 1.3 — `config.py` META validation

```python
def _validate_meta_token_relationship(self):
    has_token = bool(self.META_ACCESS_TOKEN)
    has_app = bool(self.META_APP_ID) and bool(self.META_APP_SECRET)
    if has_app and not has_token:
        raise RuntimeError(
            "META_APP_ID+META_APP_SECRET set without META_ACCESS_TOKEN — "
            "can only auto-refresh, need a starting long-lived token."
        )
    if has_token and not has_app:
        log_warning("META_ACCESS_TOKEN set without META_APP_ID/SECRET — "
                    "auto-refresh disabled; token will expire after 60 days.")
    if has_token and has_app and os.getenv("META_DEBUG_TOKEN_VALIDATE") == "1":
        # Opt-in: only when explicitly enabled, to avoid blocking startup on Meta API outage
        try:
            requests.get(
                f"https://graph.facebook.com/v18.0/debug_token"
                f"?input_token={self.META_ACCESS_TOKEN}"
                f"&access_token={self.META_APP_ID}|{self.META_APP_SECRET}",
                timeout=5,
            ).raise_for_status()
        except Exception as e:
            log_warning(f"Meta /debug_token check failed: {e} — proceeding anyway")
```

Step 1.4 — `src/audio/trending_audio.py` FALLBACK_TRACKS repair

Replace empty URLs with:
1. Jamendo CDN URLs from `JAMENDO_CLIENT_ID` query (validated by HEAD 200)
2. Local `assets/audio/fallback/{mood}.mp3` shipped from Jamendo CC-BY archive
   (verified bytes>0 on disk)

Step 1.5 — `src/analytics/competitor.py` DB_PATH

```python
DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"
```

Step 1.6 — `src/prompts/architect.py` SDK migration

```python
from anthropic import Anthropic  # module-level

class PromptArchitect:
    def __init__(...):
        self._anthropic = Anthropic(api_key=api_key) if api_key else None

    def enhance_with_claude(self, base_prompt, quote):
        if not self._anthropic:
            return base_prompt
        try:
            resp = self._anthropic.messages.create(
                model="claude-haiku-4-5",
                max_tokens=150,
                temperature=0.7,
                system=SYSTEM,
                messages=[{"role": "user", "content": USER}],
            )
            enhanced = resp.content[0].text.strip()
            ...
        except (anthropic.APIError, anthropic.APIConnectionError) as e:
            log.warning(f"[prompt-architect] SDK fallback: {e}")
            return base_prompt
```

Update `requirements.txt` if `anthropic` not already pinned ≥ 0.40.0.

### Phase 2 — Strategic prompts (Section 3 + audio wiring)

Step 2.1 — Strategist (replace `_PREFIX_DEFAULT` + `_ROLE_DEFAULT` in
`studio/strategist.py` with supplied Content Director & Chief Philosopher
template). Schema-compatible. Add 3-pillar bias: `CBT-Stoic bridge`,
`Relational/Compassionate Stoicism (hopecore)`, `Narrative historical`.

Step 2.2 — Copywriter (replace `_DRAFT_ROLE_DEFAULT` + `_REVISE_ROLE_DEFAULT`
in `studio/copywriter.py` with supplied Temporal Scripting Formula). Add
explicit emission contract for `[emotion]` tags in CTAs.

Step 2.3 — Story Writer (replace `_PREFIX` + `_ROLE_DEFAULT` in
`studio/story_writer.py` with supplied Historical Biographer template).
Preserve `EXEMPLAR_WEIRD` + `EXEMPLAR_DEBATE` blocks and
`validate_story`/`validate_formula` gates.

Step 2.4 — Audio upgrade
- Update `src/audio/elevenlabs_engine.py` VOICES dict: add josh/bill/david
  entries, update REEL_VOICE = "bill", update MOOD_VOICES
- Add `src/audio/emotion_tags.py` helper module: `_EMOTION_TAGS` set, sanitizer
  to convert `[pause]` → `<break time="0.5s" />`
- Update `src/audio/voice_director.py`: `apply_gravitas()` skip if file
  contains `<break>` tags (preserves timing); add `_emotion_tag_chapter_breaks()`
  variant

### Phase 3 — Visual upgrade (Section 5)

Step 3.1 — `src/prompts/architect.py` constants
- Add `MONUMENTALISM_COMPOSITIONS`, `MONUMENTALISM_LIGHTING`,
  `MONUMENTALISM_TEXTURES`, `MONUMENTALISM_ATMOSPHERE` (4-6 items each)
- Add `HOPECORE_*` parallel constants
- Add `PHOTOREAL_RIG` constant

Step 3.2 — Mood → style routing in `build()`
```python
DARK_MOODS = {"dark_philosophical", "dramatic_ancient", "stark_minimal", "epic_warrior"}
HOPEFUL_MOODS = {"cinematic_hopeful", "mystical_greek", "calm_stoic"}

if mood in DARK_MOODS and style != "photorealistic":
    core += _weave_digital_monumentalism()
elif mood in HOPEFUL_MOODS and style != "photorealistic":
    core += _weave_hopecore()

enhancements.append(PHOTOREAL_RIG)  # always-on
```

## 4. Data flow

```
PerformanceBrief → Strategist(CreativeBrief)
                       ↓
                  Copywriter(Concepts)
                       ↓
                  ConceptPicker(Decision)
                       ↓
                  Studio.run() ──┐
                                 ↓
              PromptArchitect.build(quote, mood)
                  ├─ mood in DARK → + Monumentalism pool
                  ├─ mood in HOPEFUL → + Hopecore pool
                  └─ always → + Photorealism Rig
                  ↓
              Emotion-tagged VO  →  ElevenLabs (bill/david/josh)
                  ├─ [pause] → <break time="0.5s" />
                  └─ voice_director.delivery_profile() scene tuning
                  ↓
              Jamendo music + audio mix → FFmpeg → MP4 → Instagram Graph API
```

## 5. Error handling

- Each fix must keep its existing failure mode (best-effort try/except where
  present). Never crash the pipeline.
- Trend Scout / Music Director / Prompt Architect: any error → silent fallback
  to legacy templated path
- ElevenLabs failure → edge-tts fallback (`AndrewNeural`)
- edge-tts failure → silent reel (caption-only)

## 6. Testing strategy

### Baseline (memory `socrates-known-gotchas.md`)

- `remotion/public/reel-data.json` mutated by `test_remotion_reel.py::test_real_render_produces_mp4` — restore post-test
- 2 pre-existing `test_reel_composer.py` failures (local libx264 env) — NOT regressions
- 2 pre-existing `Root.tsx` tsc errors (Remotion v4 typing) — NOT regressions
- Python tests run in 3.11 `.venv`

### New tests required

| File | Asserts |
|------|---------|
| `tests/test_reel_composer_transition_preservation.py` | When `beat_sync_info["transition_type"]="fade"`, final `transition_type == "fade"` (not random) |
| `tests/test_orchestrator_dry_run.py` | `dry_run=True` → `mark_posted`/`save_proposal`/Graph API all skipped, log emitted |
| `tests/test_competitor_db_path.py` | `competitor.DB_PATH` resolves to repo-root `data/pipeline.db` (not `src/data/...`) |
| `tests/test_prompt_architect_sdk.py` | Mock `anthropic.Anthropic`; verify `model="claude-haiku-4-5"` used; verify SDK error fallback to base_prompt |
| `tests/test_config_meta_validation.py` | RuntimeError on app+secret without token; warning on token without app/secret |
| `tests/test_trending_audio_fallback.py` | Every `FALLBACK_TRACKS[k]["url"]` is non-empty and (skip-if-offline) HEAD-check 200 |
| `tests/test_prompt_architect_monumentalism.py` | `dark_philosophical` mood → built prompt contains "marble"/"fog"/"shadow" token |
| `tests/test_prompt_architect_hopecore.py` | `cinematic_hopeful` mood → built prompt contains "golden"/"mist"/"rain" token |
| `tests/test_prompt_architect_photoreal_rig.py` | EVERY built prompt (any mood) ends with the Photoreal Rig substring |
| `tests/test_emotion_tag_sanitizer.py` | `[pause]` → `<break time="0.5s" />`; other tags preserved literal |
| `tests/test_elevenlabs_voices.py` | `VOICES["bill"]` resolves to a non-empty ID; `REEL_VOICE == "bill"` |

### Verification gate

1. `.venv/bin/python -m pytest tests/ -q` — green count ≥ baseline green count,
   no new failures
2. `cd remotion && npm run build` — tsc errors stay at exactly the 2 pre-existing
3. `python -c "from studio import strategist, copywriter, story_writer; from src.prompts.architect import PromptArchitect"` — import smoke
4. `git status remotion/public/reel-data.json` → restore if dirty
5. `.venv/bin/python -c "import anthropic; print(anthropic.__version__)"` → ≥ 0.40.0

## 7. Out of scope

- Adding new TTS providers (kept: ElevenLabs + edge-tts; OpenAI legacy fallback)
- Carousel content re-architecture (carousel already wired)
- Remotion scene composition (animations unchanged — only prompt inputs shift)
- Approval daemon / engagement-worker rewrites (out of upgrade scope)
- Trained/online learning rate retuning (rubric scoring unchanged)

## 8. File-touch inventory

### Modified
- `src/video/reel_composer.py` (bug fix)
- `team/orchestrator.py` (dry_run threading)
- `config.py` (meta validation)
- `src/audio/trending_audio.py` (real fallback URLs)
- `src/analytics/competitor.py` (DB_PATH)
- `src/prompts/architect.py` (SDK migration + Monumentalism/Hopecore/Rig)
- `studio/strategist.py` (prompt replacement)
- `studio/copywriter.py` (prompt replacement)
- `studio/story_writer.py` (prompt replacement)
- `src/audio/elevenlabs_engine.py` (voice roster update)
- `src/audio/voice_director.py` (gravitas skip on `<break>`)
- `tests/test_*` (new test files)

### Added
- `src/audio/emotion_tags.py` (sanitizer + tag constants)
- New tests listed in §6

### Untouched
- `studio/types.py` (schemas unchanged)
- `pipeline.py` (callers unchanged)
- `remotion/` (animation layer unchanged)
- All persistence/DB migrations
