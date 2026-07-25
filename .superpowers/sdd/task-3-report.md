# Task 3: Conditional revision stage — Report

(script-writer-v3 plan)

## Status
Complete

## Changes
- `studio/story_writer.py`:
  - Added `REVISION_THRESHOLD = 6.5`.
  - Refactored `_quote_leak` from a closure inside `write_story` to a
    module-level `_quote_leak(d, pool)`; updated both existing call sites
    (draft loop + corrective retry) to pass `pool` explicitly.
  - Added module-level `_passes_all_gates(d, mode, pool)` — the same three
    gates (`validate_story`, `validate_formula`, pool-membership) the draft
    loop already enforces, shared with the new revision path.
  - Added `_maybe_revise(client, role, winner, mode, pool, ctx)`: scores the
    rubric-picked winner via `rubric.score_story_detailed`; if it has no
    weaknesses and total >= threshold, returns it unchanged. Otherwise
    builds a subscore report (per-subscore lines + named weaknesses +
    "Rewrite the four beats fixing EXACTLY the named weaknesses. Keep every
    phrase that already works." + `json.dumps(winner)`), makes ONE
    `client.call`, and ships the revision only if it passes
    `_passes_all_gates` + the quote-leak check + scores `>=` the original
    total — otherwise the original winner ships. Whole helper wrapped in
    try/except → returns winner on any error, never raises.
  - Wired into `write_story`: right after `valid.sort()` picks the winner,
    `winner = _maybe_revise(client, role, winner, mode, pool, ctx)` before
    return. Draft-loop telemetry prints/reasons and the no-valid-draft
    corrective-retry path are untouched except for the `_quote_leak` call
    signature change.
- `tests/test_revision_stage.py`: new, 3 tests (fires-and-ships-better,
  never-worse, strong-draft-skips-revision). Fixtures tuned from the brief's
  draft (word-repeat counts and the WEAK/WORSE cta tier) so they land on the
  intended side of `REVISION_THRESHOLD` and the never-worse comparison is
  strict rather than tied — see Fixture tuning below.

## Fixture tuning (brief's NOTE)
Verified actual subscores via `rubric.score_story_detailed`:
- `WEAK`: hook=0.0 (all-abstraction hook: mindset/success/growth), cta=6.0
  ("send" but not the specific pattern), total=5.2 (< 6.5, weakness on hook)
  → fires revision.
- `STRONG_REVISION` (what the 3rd call returns in test 1): hook=8.0
  (digit "9"), cta=9.0 (specific "send this to the friend" pattern),
  total=8.96 → ships, replaces WEAK.
- `WORSE` (test 2, cta downgraded to bare "Share."): cta drops from the
  "send" tier (6.0) to the bare tier (3.0), total=4.6, strictly less than
  WEAK's 5.2 → never-worse check rejects it, original WEAK ships.
  (The brief's literal `beat_cta: "Share this post."` → `"Share."` pair
  both land in the same 3.0 cta tier and tie exactly — I changed WEAK's cta
  to the 6.0 "send"-tier so the downgrade is provably strict, per the
  brief's "fixtures tunable" note.)
- `STRONG` (test 3): hook=10.0 (digit "3" + "marble"), cta=9.0, total=9.8,
  no weaknesses → skips revision entirely (2 calls, not 3).

## Tests
- `tests/test_revision_stage.py`: FAIL (ImportError: REVISION_THRESHOLD)
  before implementation, confirmed.
- `tests/test_revision_stage.py` + `tests/test_viral_formula.py` +
  `tests/test_content_brains.py`: 29/29 passed.
- Full suite: 771/771 passed.

## Commit
```
0cb0f76 feat(script): conditional revision stage — subscore report in, never-worse out (spec 3)
```
No Co-Authored-By trailer.

## Self-review / concerns
- `_maybe_revise` is wired unconditionally for all modes, per the brief's
  literal Step 3 code (no mode guard). For `mode="punch"`,
  `score_story_detailed` requires a non-empty `beat_reframe`; punch's
  `beat_reframe` is always `""`, so `score_story_detailed` short-circuits
  to the `empty` dict (`total=0.0`, `weaknesses=[]`). `total < 6.5` is
  still true, so revision always fires for punch reels — and since the
  revised punch draft also has an empty reframe, its score is also 0.0, so
  the never-worse check (`0.0 >= 0.0`) always ships the revision. Net
  effect: every punch-mode reel now makes one extra LLM call it didn't
  before, and the revision always replaces the winner (subject only to
  `_passes_all_gates`). This matches the brief exactly as given (no
  punch-mode exclusion was specified) but is worth a decision: either
  accept the extra punch-mode call, or scope `_maybe_revise` to
  `mode != "punch"` in a follow-up. Did not add that guard myself since it
  wasn't in the brief and no punch-mode test exists to pin the intended
  behavior — flagging for the plan owner instead of silently changing scope.
- No other concerns; full suite green, gates/telemetry for the draft loop
  unchanged.

## Follow-up fix (2026-07-21)
Applied the flagged punch-mode guard: `_maybe_revise` now returns `winner`
early when `mode == "punch"`, skipping the subscore path entirely. This avoids
wasting an Opus call and prevents tie-swapping the winner. Test added:
`test_punch_mode_skips_revision` verifies 2 calls (drafts only, no revision).
Commit: `c28742a`.
