# Plan: fix Telegram approval, ship one high-quality reel to IG, apply quality upgrades

Date: 2026-07-16
Goal: (1) make the existing Telegram approve button actually work, (2) generate and
post ONE well-edited reel to Instagram end-to-end, (3) apply the highest-impact
quality improvements from `docs/quality_improvement_plan.md` and `CRITIQUE.md` so
future reels are visibly better.

Repo: `/Users/utsab1/Documents/socrates automation`
User confirmed: format = Reel, philosophy = pipeline-picks from quotes.xlsx,
post = LIVE (Meta token set).

---

## Phase A — Diagnose the Telegram approval bug (no fix yet)

Confirmed by reading `src/core/approval.py` + `pipeline.py`:
- `notify_manual_reel_ready(...)` (pipeline.py:1229, 814) sends the reel with
  `approve_<post_row_id>` / `reject_<post_row_id>` inline buttons.
- The buttons write callback_queries to Telegram's `getUpdates` queue.
- `approval.poll_once()` is the ONLY thing that drains the queue and records the
  decision into `data/approvals.json`.
- **Nothing schedules `poll_once()`**. The CI workflow ends after `notify_manual_reel_ready`.
  Manual taps in Telegram sit in the queue until `python -m src.core.approval --poll`
  is run by hand.

Result: every tap you do in Telegram is silently dropped. No "approve" gets recorded,
so `get_decision(post_row_id)` returns `None` forever, and the reel never gets posted
by the (also-missing) "auto-post on approval" step.

Two design-level problems behind that:
1. **No poll daemon** — need a way to keep `poll_once` running continuously.
2. **No "post on approval" handler** — even after approval is recorded, nothing
   takes that approval and posts the reel to IG. The pipeline's manual path
   (`pipeline.py:809-828`) sends the reel and stops — it never re-enters to do
   the publish when a human taps ✅ later.

Fixes in Phase B.

---

## Phase B — Fix Telegram approval end-to-end

B1. **Drain-on-arrival daemon**: add a `src/core/approval_daemon.py` that runs
    `poll_once()` every 2s with `timeout=2`, writes decisions to `data/approvals.json`,
    and persists offset correctly (the existing `poll_once` already does this —
    just wrap it in a loop with signal handling).

B2. **Auto-post on approval**: add `src/core/approval_poster.py` that watches
    `data/approvals.json` for new `approved` reel decisions (status=approved,
    applied=false, key is digit-only), then looks up the pending reel record
    (from `data/pipeline.db` — already keyed by post_row_id, has reel path and
    caption) and posts it via the existing `post_reel_to_instagram` call. This
    is the missing piece.

B3. **Single-process combined watcher**: merge B1+B2 into `approval_daemon.py`
    so the user runs ONE background process. Keep them as two functions so
    they can be invoked separately from cron too.

B4. **Verify with one synthetic approval**: write a tiny test that injects a
    fake callback_query into a mocked getUpdates call → confirms the daemon
    records the decision correctly and the auto-poster triggers.

---

## Phase C — Generate + LIVE-post one reel (the user's main ask)

C1. Pick a quote: `--content` JSON with hand-curated hook, quote, caption,
    CTA, hashtags, mood (still from the philosophy angle user said
    "pipeline picks" — so let the bandit choose from `quotes.xlsx`, but the
    bandit's record tells us which mood/hook-type/format have historically
    worked best).

C2. Render via the Remotion path (highest quality currently in the codebase —
    see CLAUDE.md "Reel flow"). Use the latest commit on main.

C3. Inspect the output MP4 for quality issues:
    - does the sage voice land? (`en-US-AndrewNeural`, rate -30%, pitch -14Hz)
    - is the burned-in subtitle readable?
    - is the bridge scene present and well-paced?
    - any visible ffmpeg warnings in the render log?

C4. Send to Instagram via `post_reel_to_instagram` directly (not via manual
    path — user wants LIVE post, not wait for approval). Confirm post_id
    non-null in the response.

C5. Verify post landed on the real IG account. The notifier already sends a
    `post_published` Telegram message with the IG permalink — confirm that
    fires and the link resolves.

---

## Phase D — Apply highest-impact quality improvements

Picked from `docs/quality_improvement_plan.md` and the OPEN items in
`CRITIQUE.md` (A1-A4 fixed, B3/B4/B5 open, C2 open, D1 fixed in Phase 1, D2/D3 open,
E1-E5 open, F1-F3 open, plus the recurring complaint "captions look templated").

Ranked by impact-per-hour, low-risk first:

D1. **[HIGH ROI, ~30min]** Burned-in captions on Reels (QIP §3 item 2).
    ffmpeg `drawtext` overlay on the quote scene — addresses "85% of Reels
    watched on mute". Currently the script already does some text in Remotion,
    but is it captioned well? Need to verify, and if not, add a real
    word-by-word caption track synced to the VO.

D2. **[HIGH ROI, ~20min]** Stronger Ken Burns zoom + pan (QIP §3 item 1).
    `0.0004/frame → 1.12× over 15s` with sine pan. Currently `0.0004` is
    essentially static. If the reel is using Remotion, this concern may
    already be addressed — verify first.

D3. **[HIGH ROI, ~15min]** Better ffmpeg encoding (QIP §3 item 5).
    `preset=slow`, `crf=20`, `30fps`. Visual quality win, +30% file size
    (still tiny).

D4. **[MEDIUM ROI, ~20min]** Smart attribution (QIP §2 item 6).
    If quote is from `quotes.xlsx` use real author (Marcus Aurelius etc),
    not "Socrates" for every quote. Looks more credible to viewers.

D5. **[MEDIUM ROI, ~30min]** Dynamic CTA rotation (QIP §5 item 4).
    6 variants, rotate per post so feed doesn't read as templated.

D6. **[MEDIUM ROI, ~20min]** Hashtag + emoji generation (QIP §5 items 2+3).
    The caption already has hashtags but they look hand-curated. AI-generate
    3-5 per post, audience-aware.

D7. **[CRITICAL ROI, ~15min]** Increase Reel IG publish wait timeout (CRITIQUE B5).
    `_wait_for_container` default `max_wait=60` → 180s. Reel containers
    routinely take >60s. Without this, every other Reel crashes.

D8. **[MEDIUM ROI, ~45min]** Auto-claim-on-success (CRITIQUE B5).
    Don't claim the day's slot via `save_post` until publish actually succeeds.
    Today: claim → publish → crash leaves the slot burned.

D9. **[LOW ROI but easy, ~15min]** Deduplicate the engagement-score formula
    (CRITIQUE F1). One canonical `SCORE_WEIGHTS` constant, import where
    needed. Keeps predictions/cohorts/optimizer in sync.

D10. **[MEDIUM ROI, ~30min]** Increase inference steps + negative prompt
    (QIP §1 items 2+3). FLUX goes from 4 → 6 steps, add
    "modern objects, text, watermark, people, faces, hands" negatives.
    Visible quality win on the BG images.

---

## Phase E — Verify & document

E1. Render the new reel after D1-D6 land. Compare visually to the
    pre-improvement reel at `output/reel_015.mp4`.

E2. Run the full test suite, confirm no regressions (currently 561 passing).

E3. Update `docs/quality_improvement_plan.md` to mark the items actually
    shipped in this pass, with commit SHAs.

E4. Update `CLAUDE.md` if any new gotchas emerged.

---

## What this plan DOES NOT do (out of scope today)

- Phase 3-4 (weight_fit, visual prompt asset cache) — separate session
- Full re-render of all historical reels
- A/B test framework overhaul (QIP Phase 5)
- Telegram bot polish beyond approval fix
- Carousel improvements (only reel + image feed post improvements)
- New optimizer champion wiring (CRITIQUE B3) — the optimizer pipeline
  is functional, this is wiring, not content quality

---

## Estimated effort

| Phase | Time  | Risk |
|-------|-------|------|
| B     | 1.5h  | low  — pure orchestration, existing code reusable |
| C     | 30m   | low  — pipeline already supports `--content` JSON |
| D1-D6 | ~2h   | low  — additive ffmpeg + text changes, fallbacks preserved |
| D7    | 5m    | low  — constant change |
| D8    | 45m   | medium — refactor of claim flow, needs test |
| D9    | 15m   | low  — import-only refactor |
| D10   | 30m   | low  — config change |
| E     | 30m   | low  — doc updates |
| **Total** | **~6h** |  |

---

## Execution order

1. Phase B first — the user explicitly said the approval button is broken.
2. Phase C — deliver the ONE reel + post it (this is the headline ask).
3. Phase D — apply quality wins to future reels.
4. Phase E — verify, document.

Per CLAUDE.md rules: keep files under 500 lines, validate input at system
boundaries, never crash a reel (every optional stage stays try/except
best-effort), and the `--content` JSON path stays the primary entrypoint
for hand-curated content.
