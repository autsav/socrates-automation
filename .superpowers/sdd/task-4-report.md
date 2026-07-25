# Task 4 report: 8-angle hook specialist

(Note: this path previously held a report for a different Task 4 from an
earlier plan iteration — `material_key` tracking. This report replaces it
per this task's explicit report-path instruction, same as that report noted
when it replaced an even earlier one.)

## Summary

Implemented `studio/hook_specialist.py` (8-angle hook variant pass, coded
validation + `score_hook` pick, fallback-safe), wired it into
`studio/story_writer.py` at both post-gate success paths, added the
`hook_specialist` role rows to `studio/settings.py`, and updated call-count
assertions across three test files (one more than the brief anticipated —
see Deviation).

## Steps taken

1. **Red**: wrote `tests/test_hook_specialist.py` verbatim from the brief.
   `pytest tests/test_hook_specialist.py` → `ModuleNotFoundError: No module
   named 'studio.hook_specialist'` (confirmed failing as expected).

2. **Green**:
   - Verified `_obj(props, required)` in `studio/types.py:133-135`
     (`{"type": "object", "additionalProperties": False, "properties":
     props, "required": required}`) matches the brief's `_HOOKS_SCHEMA`
     call exactly — no adjustment needed.
   - Verified `score_hook(hook: str) -> float` in `studio/rubric.py:125`
     matches the import used.
   - Created `studio/hook_specialist.py` — module copied verbatim from the
     brief: `HOOK_ANGLES` 8-tuple, `generate_hooks(client, story, n=8)`
     (try/except → `[]`), `_valid` (viewer token via
     `re.findall(r"[a-z']+", ...)`, ≤15 words, no trailing `?`, no
     resolution phrase), `pick_hook(candidates, fallback)` (max by
     `score_hook` over valid survivors, else fallback).
   - `studio/settings.py`: added `"hook_specialist": "claude-sonnet-4-6"`
     to `ROLE_MODELS` and `"hook_specialist": "medium"` to `ROLE_EFFORT`
     (both rows — the documented KeyError gotcha).
   - `studio/story_writer.py`: added a `_hook_pass(client, story, mode)`
     helper (DRY, per task context's suggestion) directly above
     `_quote_leak`. No-ops for `mode == "punch"`; otherwise imports
     `generate_hooks`/`pick_hook` and reassigns `story["beat_hook"]`,
     inside its own try/except (never raises) — functionally identical to
     the brief's inline try/except snippet, just factored into one place
     used at both call sites instead of duplicated.
     Wired at both success returns:
     - winner path (after `_maybe_revise`): `return winner` →
       `return _hook_pass(client, winner, mode)`.
     - corrective-retry success path: `return d` →
       `return _hook_pass(client, d, mode)`.
     The `None`-returning failure paths (both drafts + retry all reject)
     are untouched — the hook pass only ever runs on a story that already
     shipped.

3. **Call-count fallout** (hook pass = +1 `client.call` per successful
   non-punch `write_story` return):
   - `tests/test_revision_stage.py::test_revision_fires_and_ships_better`:
     `len(calls) == 3` → `4` (2 drafts + 1 revision + 1 hook pass), per brief.
   - `tests/test_revision_stage.py::test_strong_draft_skips_revision`:
     `len(calls) == 2` → `3` (2 drafts, no revision, +1 hook pass), per brief.
   - `test_revision_never_worse` / `test_punch_mode_skips_revision`: no
     count assertions, or punch-guarded — untouched.
   - **Not anticipated by the brief**: `tests/test_content_brains.py::
     test_write_story_two_drafts_rubric_picks_winner` also asserts
     `len(calls) == 2` (2 drafts, winner scores high enough to skip
     revision). Same root cause; updated to `3` with comment
     `# 2 drafts + 1 hook pass`. The mock ignores the `role` param, so the
     hook-pass call resolves through the same class; its return dict has no
     `"hooks"` key → `generate_hooks` returns `[]` → `pick_hook` falls back
     to the unchanged winning hook, so the `beat_hook.startswith("He
     slept")` assertion still holds.
   - Failure-path tests (`tests/test_viral_formula.py::
     test_quote_leak_rejected`, `test_quote_row_out_of_pool_rejected`)
     return `None` before the hook-pass call site — untouched, counts
     still 3.
   - Grepped all of `tests/` for `len(calls)` / `calls[` alongside the
     full-suite run to confirm no other `write_story` call-count assertion
     was missed.

4. **Tests**:
   - `pytest tests/test_hook_specialist.py tests/test_revision_stage.py
     tests/test_punch_arc.py tests/test_viral_formula.py -q` → `27 passed`.
   - Full suite: `pytest -q` → `777 passed, 1 warning` (pre-existing
     `starlette`/`httpx` deprecation warning, unrelated).

## Commit

```
428b02d feat(script): 8-angle hook specialist pass with coded pick (spec 4)
```
Staged: `studio/hook_specialist.py`, `studio/story_writer.py`,
`studio/settings.py`, `tests/test_hook_specialist.py`,
`tests/test_revision_stage.py`, and `tests/test_content_brains.py`
(deviation — see below). `git status --porcelain` after commit shows
nothing staged from this task; the repo's other dirty files (task
report/brief markdowns for tasks 1/2/3/5/6/7/8/9, `logs/notifications.jsonl`,
`output/product/landing.html`, `quotes.xlsx`,
`remotion/public/reel-data.json`, `.hermes/`, new `remotion/public/bg*.mp4`)
are pre-existing unrelated churn from other in-flight work — verified via
`git status --porcelain` before staging, left untouched. `data/pipeline.db`
not touched/staged (untracked, per project convention). No `Co-Authored-By`
trailer — confirmed via `git show -s --format='%B' HEAD`.

## Deviation from the brief

The brief's `git add` list was `studio/hook_specialist.py
studio/story_writer.py studio/settings.py tests/test_hook_specialist.py
tests/test_revision_stage.py`. I added `tests/test_content_brains.py` to
that set because it has its own strict `write_story` call-count assertion
that the hook-pass wiring breaks (see above) — omitting it would leave a
failing test in the working tree with no fix committed, i.e. the suite
would not actually be green *at* this commit. Flagging in case the
orchestrator wanted that split into its own commit instead.

## Self-review

- `_HOOKS_SCHEMA` matches `_obj`'s real 2-arg signature — confirmed by
  reading `studio/types.py` before writing the module.
- Both `ROLE_MODELS` and `ROLE_EFFORT` got the `hook_specialist` row.
- Wiring guards `mode != "punch"` and never raises.
- `pick_hook`'s fallback returns the *original* hook unchanged on any
  failure/all-invalid-candidates, so a broken specialist can never corrupt
  or blank `beat_hook`. When a replacement does win, it satisfies
  `validate_formula`'s viewer/statement/no-question/no-resolution checks by
  `_valid`'s construction (mirrors `_SECOND_PERSON`/`_RESOLUTION_PHRASES`
  logic already in `story_writer.py`).
- `_hook_pass` is a small, single, DRY choke point used at both call sites
  rather than duplicated inline try/except blocks.

## Concerns

- See Deviation above — the extra file in the commit.
- No other concerns; no secrets/credentials touched, changes scoped to
  `studio/` and `tests/`.

## Post-task code review fix (2026-07-21)

**Issue**: `hook_specialist.py::_RESOLUTION` (4 phrases) drifted from
`story_writer.py::_RESOLUTION_PHRASES` (6 phrases). Hooks containing
"this means"/"the secret is" slipped past `pick_hook` but failed
`validate_formula`.

**Fix** (commit `a2ac7ee`):
- Added `RESOLUTION_PHRASES` constant to `studio/rubric.py` (6 phrases, single
  source of truth).
- Updated `rubric.score_hook()` to use the constant instead of inline 4-phrase
  loop.
- Imported `RESOLUTION_PHRASES` in `story_writer.py` and removed private
  `_RESOLUTION_PHRASES`; updated both usages to reference the constant.
- Imported `RESOLUTION_PHRASES` in `hook_specialist.py`, removed private
  `_RESOLUTION`, updated `_valid()` to check all 6 phrases.
- Added `test_resolution_set_matches_formula_gate()` verifying "this means"
  and "the secret is" are caught by the gate.
- All 778 tests pass.
