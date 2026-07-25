# Task 2: Quote pool + chosen-row swap — Self-Review Report

## Status: GREEN

## Commit

- `cb39cb1` — `feat(script): real quote pool — the writer picks the earned twist (spec 2)`
  (files: `pipeline.py`, `tests/test_quote_pool.py`)

## What changed

- `pipeline.py`: added `_quote_pool(quote_data) -> list[dict]` — today's row first
  (from `quote_data`), then up to 19 more unposted rows pulled via
  `studio.run._build_pool(str(EXCEL_PATH))`, each entry `{row_number, quote,
  attribution}`. Any exception (bad excel, missing file, etc.) → single-row
  fallback `[today]`. Never raises.
- `_build_story_beats`: pool construction replaced —
  `pool = [{"row_number": row or 0, "quote": quote_data.get("quote", "")}]`
  → `pool = _quote_pool(quote_data)`.
- After the story passes safety checks (`is_unsafe`, `mentions_named_person`)
  and `story["mode"]`/`story["material_key"]` are stamped, added the
  chosen-row swap: look up `story.get("quote_row")` in `pool`; if found and
  different from `quote_data`'s current row, overwrite `quote_data["quote"]`,
  `["attribution"]`, `["row_number"]` with the chosen entry's values. This is
  the intentional redirect the brief calls out — downstream excel marking
  keys off `quote_data["row_number"]`, so the swap makes the *chosen* row the
  one that gets marked posted, not the day's assigned row.

## Attribution column check

Read `src/core/excel_reader.py`'s column mapping (cols A-I: `#`, Quote,
Audience, Caption, Caption Variant B, [F unused], Status, Posted Date, Post
ID) and `studio/run.py:_build_pool` (reads cols A/B/C only: row_number, quote,
audience). **No attribution column exists in the sheet.** Per the brief,
"otherwise the '— Socrates' default stands" — so `studio/run.py` was left
untouched; `_quote_pool` supplies `attribution.get("attribution", "—
Socrates")` as the default for every pool entry (both `today` and rows from
`_build_pool`, via `r.get("attribution", "— Socrates")` since `_build_pool`'s
dicts never carry that key).

## Test Summary

- **Written first, confirmed FAIL**: `AttributeError: module 'pipeline' has
  no attribute '_quote_pool'` on all 3 tests before implementation.
- **Targeted** (`tests/test_quote_pool.py`): 3 passed
  - `test_quote_pool_today_first_and_capped` — today's row is `pool[0]`, size
    capped at ≤20.
  - `test_quote_pool_failure_falls_back` — `_build_pool` raising → single-row
    fallback pool.
  - `test_chosen_row_swaps_into_quote_data` — fake `write_story` returns
    `quote_row: 12`; monkeypatched `pipeline._quote_pool` supplies row 12 in
    the pool; after `_build_story_beats` runs, `quote_data` is mutated in
    place to row 12's quote/attribution/row_number.
- `tests/test_viral_arcs.py`: 8 passed
- `tests/test_material_tracking.py`: 4 passed
- **Full suite**: 768 passed, 1 pre-existing warning (unrelated
  httpx/starlette deprecation).

## Self-review

- Diff matches the brief's snippets verbatim (`_quote_pool` body, pool
  assignment, swap block placed after safety checks + `mode`/`material_key`
  stamping, before `return story`).
- Verified the pool-membership gate in `studio/story_writer.py` (lines
  ~294-317: `not any(p["row_number"] == d.get("quote_row") for p in pool)` →
  reject) keys off `row_number`, which every `_quote_pool` entry carries —
  chosen rows validate correctly.
- Verified the swap comparison order: `chosen["row_number"] !=
  quote_data.get("row_number")` is evaluated *before* `quote_data` is
  mutated, so same-row picks (writer keeps today's quote) correctly skip the
  swap — no self-overwrite, no stale comparison.
- `git add` staged only `pipeline.py` + `tests/test_quote_pool.py`
  (`studio/run.py` untouched, correctly excluded since no attribution column
  was added there). Confirmed via `git status --short` before commit that no
  other modified/untracked files (`quotes.xlsx`, `data/pipeline.db`,
  `.hermes/`, `remotion/public/bg*.mp4`, other `.superpowers/sdd/*` reports
  from concurrent task runs, etc.) were swept in.
- No `Co-Authored-By` trailer in the commit (confirmed via `git show`).
- `data/pipeline.db` never touched, never staged.

## Concerns

- None blocking. Note for future work: since no attribution column exists in
  `quotes.xlsx`, every non-today pool entry silently defaults to "— Socrates"
  attribution even if the underlying quote is from a different Stoic (e.g.
  Marcus Aurelius, Seneca). This is spec-compliant per the brief's fallback
  instruction, but if quotes.xlsx later gains a real attribution column, both
  `studio/run.py:_build_pool` and `pipeline._quote_pool`'s `r.get(...)` calls
  should be revisited to read it.
