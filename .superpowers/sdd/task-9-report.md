# Task 9 Report: Digest injection into agent calls

## Summary

Wired `digest_text(view)` (Task 8) into all three writer agents (copywriter,
strategist, story_writer) exactly per the brief, and wired `write_story`'s
existing `extra_context` param (Task 3) into `pipeline._build_story_beats`.

## Files changed

- `studio/copywriter.py` — `draft(..., extra_context="")`: appends
  `f"\n{extra_context}"` to the user message when non-empty.
- `studio/strategist.py` — `make_brief(..., extra_context="")`: same pattern.
- `studio/run.py` — `run_studio` now fetches `digest_text("copywriter")` and
  `digest_text("strategist")` inside a `try/except Exception` (best-effort;
  falls back to `""` on any error) and passes them as `extra_context` to
  `make_brief` / `draft`, unconditionally (per brief — no emptiness gating
  beyond the kwarg's own `if extra_context:` check inside each agent).
- `pipeline.py` `_build_story_beats` — fetches `digest_text("story_writer")`
  in a `try/except Exception` right before the `write_story` call, passes it
  as `extra_context`.
- `tests/test_digest_injection.py` — new, exactly as specified in the brief:
  `test_copywriter_appends_digest_to_user_message` and
  `test_empty_context_leaves_message_unchanged`.

## TDD

1. Wrote `tests/test_digest_injection.py` first. Ran it before implementing:
   `test_copywriter_appends_digest_to_user_message` FAILED with
   `TypeError: draft() got an unexpected keyword argument 'extra_context'`
   (as expected). `test_empty_context_leaves_message_unchanged` passed
   trivially (no kwarg used).
2. Implemented the four production-file changes per the brief's code blocks
   verbatim.
3. Re-ran targeted tests
   (`test_digest_injection.py test_studio_strategist.py
   test_studio_copywriter.py test_studio_run.py`) — 11 passed.
4. Ran full suite — 2 pre-existing-passing tests broke:
   `tests/test_viral_arcs.py::test_build_story_beats_weird_mode` and
   `::test_build_story_beats_debate_when_no_trend`. Both monkeypatch
   `studio.story_writer.write_story` with a local `fake_write(client, mode,
   material, pool)` (no `**kwargs`), which broke once `_build_story_beats`
   started calling `write_story(..., extra_context=extra)`. Fixed by adding
   `extra_context=""` to both fake signatures (2-line test change, no
   assertion changes) — consistent with how `test_studio_run.py` already
   mocks with `lambda *a, **k`.
5. Full suite re-run: **687 passed**, 0 failed.

## Commit

**Deviation from the literal brief command**: the specified `git add` list
(`studio/copywriter.py studio/strategist.py studio/run.py pipeline.py
tests/test_digest_injection.py`) does not include `tests/test_viral_arcs.py`.
Committing only that list would have left a necessary test fix uncommitted in
the working tree — meaning a fresh checkout at this commit would have 2
failing tests. Since the task explicitly required "full suite green" before
committing, I added `tests/test_viral_arcs.py` to the `git add` alongside the
brief's list, keeping the exact same commit message. No other files were
touched; `data/pipeline.db` was dirtied by the test run and `git checkout
--`'d before staging — not part of the commit.

Commit: `ca2ddfd` — "feat(loop): inject performance digest into writer agents
(spec 2.2 + C)" — 6 files changed (the 5 brief files + `test_viral_arcs.py`),
69 insertions(+), 9 deletions(-). No `Co-Authored-By` trailer.

## Self-review

- `digest_text` never raises (per Task 8 contract) — the `try/except` wraps
  around it anyway per the brief's defensive style; harmless belt-and-braces.
- Cold-start digest returns `"No performance data yet."` and is passed
  unconditionally as `extra_context` — per task instructions, no emptiness
  check was added beyond what each agent's own `if extra_context:` already
  does (which is true/non-empty for that string, so it does get appended —
  intentional, matches the brief).
- Existing callers of `make_brief`/`draft` using positional args are
  unaffected — new params are appended at the end of each signature with
  defaults.
- Diff matches the brief's code blocks verbatim (checked with `git diff`).
- No files outside the intended scope were incidentally modified.

## Concerns

- The `tests/test_viral_arcs.py` fix (adding `extra_context=""` to two mock
  signatures) was necessary collateral from this change but sits outside the
  brief's literal file list — flagged above rather than silently expanded.
- `digest_text("copywriter")` / `digest_text("strategist")` /
  `digest_text("story_writer")` view names are used as given in the brief;
  did not re-derive/validate them against Task 8's internal view-name schema
  beyond confirming `digest_text(view, db_path=DEFAULT_DB) -> str` never
  raises.
