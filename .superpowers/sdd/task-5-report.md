# Task 5 Report: Winner learning + gate (script-writer-v3 plan)

Commit: `0bd35ca` — "feat(script): winner learning — real top scripts feed the writer (spec 5)"

> Note: this file previously held a report for a different, earlier-numbered
> Task 5 (scene-level animation effects — cascade quote, end ticks, ghost
> trail, CTA freeze-pop, commit `0ce6a4d`) from the "real-sync plan" SDD.
> That work is already merged to main and untouched by this task; this report
> replaces the stale content with the current Task 5 (winner learning, per
> `.superpowers/sdd/task-5-brief.md`, script-writer-v3 plan), following the
> same convention that earlier report used for its own predecessor.

## Step 1: Failing test

Wrote `tests/test_winner_learning.py` per the brief verbatim (`_seed` fixture,
`test_below_three_scored_returns_empty`, `test_top_two_by_sends`), and
realized the brief's stubbed third test (`test_record_script_roundtrip`) by
copying the monkeypatch/insert/assert pattern from
`tests/test_material_tracking.py::test_migration_and_roundtrip`: monkeypatch
`data_store.DB_PATH` to a tmp db, `init_db()`, insert a bare post row, call
`record_script(1, {"hook": "h"})` then `record_script(1, None)` (asserted
no-op/never-raises), then a direct `SELECT script_json FROM posts` to assert
the JSON round-trips.

Ran `pytest tests/test_winner_learning.py` → **FAIL**, `ImportError: cannot
import name 'winning_scripts' from 'src.analytics.performance_digest'`, as
expected before implementation.

## Step 2: Implementation

**`src/core/data_store.py`** — mirrors the `material_key`/`record_material`
shape exactly:
- Guarded `ALTER TABLE posts ADD COLUMN script_json TEXT DEFAULT NULL`
  migration in `init_db()`, added right after the existing `material_key`
  migration block.
- `record_script(row_id: int, script: dict | None) -> None`: `if not script:
  return` (falsy — `None` or `{}` — no-ops), else `UPDATE posts SET
  script_json = json.dumps(script) WHERE id = ?`, same
  try/except-pass/finally-close connection style as `record_material`.

**`src/analytics/performance_digest.py`** — added `winning_scripts(n=2,
db_path=DEFAULT_DB) -> list[dict]` per the brief's exact block: joins
`posts`/`post_metrics` on `post_id`, filters `dry_run=0 AND script_json IS
NOT NULL AND reach >= 100`, parses each `script_json`, computes
`sends_per_reach = round(shares/reach, 4)`, returns `[]` when fewer than 3
scored scripts exist, otherwise the top `n` sorted descending. Whole function
wrapped in try/except returning `[]` (learning is optional, never breaks the
pipeline).

**`pipeline.py`**:
- Import: added `record_script` to the `src.core.data_store` import line
  (line 29) alongside `record_arc`, `record_material`.
- `_run_pov_reel` story-beat mapping block (`if story is not None:` branch,
  where `hook_text`/`cta_text`/`bridge` get set from `story`): added
  `quote_data["script"] = {"hook": hook_text, "reframe":
  story["beat_reframe"], "cta": cta_text}` — only set when a story arc
  actually shipped, per the interface spec.
- Publish block (beside `record_arc`/`record_material`, guarded on
  `post_row_id is not None`): added `record_script(post_row_id,
  quote_data.get("script"))`.
- `_build_story_beats`: after the existing `digest_text("story_writer")`
  call that builds `extra`, added the winners block per the brief verbatim —
  best-effort `try/except`, fetches `winning_scripts(2)`, and if any winners
  exist appends a `"REAL WINNERS FROM THIS ACCOUNT (study what worked):"`
  block with each winner's hook / first-60-words-of-reframe / cta to `extra`
  before it's passed to `write_story(...)`.

## Step 3: Verification

- `.venv/bin/python -m pytest tests/test_winner_learning.py
  tests/test_material_tracking.py tests/test_performance_digest.py -q` →
  **12 passed**.
- `.venv/bin/python -c "import pipeline"` → clean import, no syntax/import
  errors from the new wiring.
- Full suite: `.venv/bin/python -m pytest -q` → **781 passed**, 1
  pre-existing warning (starlette/httpx deprecation, unrelated).

## Commit

`0bd35ca` — `feat(script): winner learning — real top scripts feed the
writer (spec 5)`. Files staged exactly as instructed: `src/core/data_store.py`,
`pipeline.py`, `src/analytics/performance_digest.py`,
`tests/test_winner_learning.py`. No `Co-Authored-By` trailer. `data/pipeline.db`
was not touched/staged. Pre-existing unrelated working-tree modifications
(other task reports/briefs, `logs/notifications.jsonl`, `quotes.xlsx`,
`output/product/landing.html`, `remotion/public/reel-data.json`, untracked
`.hermes/` and `remotion/public/bg*.mp4`) were left untouched and unstaged.

## Self-review

- **`record_script` falsy no-op.** `if not script: return` covers both
  `None` and `{}` (falsy dict) before any DB connection is opened, matching
  `record_material`'s `if not key: return` shape and the brief's "falsy →
  no-op" spec exactly.
- **Migration ordering/idempotency.** The `script_json` ALTER checks
  `"script_json" not in post_columns` (computed once via `PRAGMA
  table_info(posts)` earlier in `init_db()`), so re-running `init_db()` on an
  already-migrated DB is a no-op — same guard pattern as every other
  migration in the file. Verified indirectly: the full suite (which calls
  `init_db()` repeatedly across many tests reusing tmp DBs and the real
  schema) passed with no duplicate-column errors.
- **`winning_scripts` gate correctness.** With `n_scored=2` the function
  correctly returns `[]` (below the 3-scored floor) even though both rows
  individually pass the `reach >= 100` and `script_json IS NOT NULL` filters
  — confirmed by `test_below_three_scored_returns_empty`. With 5 scored the
  ranking by `sends_per_reach` descending picks `hook4`/`hook3` in order,
  confirming the SQL join + sort + slice is correct, not just non-crashing.
  Each `json.loads` failure is caught per-row (`continue`) rather than
  aborting the whole query, so one corrupt `script_json` row can't zero out
  the winners for all other rows.
- **Pipeline wiring is best-effort at both points.** `record_script` is
  wrapped internally in try/except like its siblings, so a DB hiccup during
  publish can't crash a reel. The winners-injection block in
  `_build_story_beats` is wrapped in its own try/except separate from the
  `digest_text` try/except immediately above it — an exception building the
  winners block (e.g. `winning_scripts` returning malformed data, though its
  own try/except should prevent that) can't wipe out an `extra` string
  `digest_text` already successfully produced, since `extra` was already
  assigned before the winners block runs and the winners block only ever
  appends to it inside its own guarded try.
- **`quote_data["script"]` only set on a real story arc.** It's assigned
  inside the `if story is not None:` branch of `_run_pov_reel`, not the
  `else` (plain-arc) branch, matching "when a story arc shipped" in the
  interface spec — non-story arcs simply never populate
  `quote_data["script"]`, so `record_script(post_row_id,
  quote_data.get("script"))` no-ops for them via the falsy-check in
  `record_script`, without needing a separate `is not None` check at the
  call site.
- **No `data/pipeline.db` mutation risk.** All new code paths (`record_script`,
  `winning_scripts`) only touch `DB_PATH`/`DEFAULT_DB` at call time (never at
  import time), and no test in `test_winner_learning.py` uses the real DB —
  all three tests operate on `tmp_path` databases (either raw sqlite via
  `_seed`/direct `sqlite3.connect`, or `data_store.DB_PATH` monkeypatched).

## Files touched

- `/Users/utsab1/Documents/socrates automation/src/core/data_store.py`
- `/Users/utsab1/Documents/socrates automation/pipeline.py`
- `/Users/utsab1/Documents/socrates automation/src/analytics/performance_digest.py`
- `/Users/utsab1/Documents/socrates automation/tests/test_winner_learning.py`

## Status

DONE

---

## Post-delivery review fixes (commit 568f848)

Fixed two review findings discovered after delivery:

1. **Recorded script hook divergence**: `pipeline.py` line 1004 was storing untrimmed hook text to `quote_data["script"]["hook"]` before enforcement at render (line 1151). Scripts were recording 13–15 word hooks instead of the enforced ≤12. **Fix**: Store enforced value at script assembly: `"hook": _enforce_hook_len(hook_text)`.

2. **Empty-reframe pollution**: `winning_scripts()` returned punch scripts (empty reframe) as exemplars. Useless for teaching craft; broke the learning loop intent. **Fix**: Skip entries in the scored loop where reframe is empty/whitespace: `if not (s.get("reframe") or "").strip(): continue`.

Tests: added `test_empty_reframe_scripts_excluded` to `tests/test_winner_learning.py` — verifies top scorer with empty reframe is excluded from winners output.

Verification: `.venv/bin/python -m pytest tests/test_winner_learning.py tests/test_quote_pool.py -q` → 7 passed. Both review findings resolved.
