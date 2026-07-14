# Critique — 2026-07-14

> **Update (same day):** Section A criticals **A1-A4 FIXED** (commit 423e098). **B2 FIXED** + **B1 evaluation engine built & tested** (commit 8e86f4b) — only live-pipeline arm-serving wiring remains. Full suite 539 pass.

Supersedes the 2026-07-11 critique (several of those findings are now fixed — e.g. `analytics.yml` uses `git add -f`). Scope: full pipeline (`pipeline.py`, `config.py`, `src/core/*`), studio agents (`studio/*`), analytics + predictive scoring (`src/analytics/*`, `src/video/predictive_scoring.py`), the **new self-improving loop** (`src/optimizer/*`, `optimize.py`), CI workflows, security surface, and test suite (517 tests). Findings verified against source; `file:line` from the tree as it stands today on branch `feat/self-improving-loop`.

Legend: **[C]** critical · **[H]** high · **[M]** medium · **[L]** low. `OPT-*`/`optimizer` = new self-improving-loop code (self-review); the rest is existing code.

---

## A. Critical Bugs (must fix before production)

### A1 ✅ FIXED [C] Telegram approve/reject namespace is shared between reels and the optimizer → wrong promotions + lost approvals
**`optimize.py:26` + `src/core/approval.py:44-46,68-115` + `pipeline.py:764,1170`.**
Reels send `approve_<post_row_id>` / `reject_<post_row_id>`; the optimizer sends `approve_<challenger_version_id>` / `reject_<challenger_version_id>`. Both flow through the **same** `_CALLBACK_RE = ^(approve|reject)_(\d+)$`, the **same** `poll_once()` (returns `{"post_row_id": int}`), and the **same** shared offset + `decisions{}` map in `approval.json`. `post_row_id` (from `posts`) and `challenger_version_id` (from `opt_versions`) are **independent autoincrement sequences that both start at 1 → they collide.**
- **Failure scenario 1 (wrong write):** a reel posts with `post_row_id=7`, you tap ✅. `optimize.py --apply-decisions` polls, gets `{post_row_id: 7}`, calls `loop.apply_decision(7, True)` → **promotes optimizer challenger version 7**, an unrelated prompt, live.
- **Failure scenario 2 (lost approval):** whichever job calls `poll_once` first advances the shared offset and marks the update consumed, so the other flow's approvals silently vanish. The reel manual-approval flow and the optimizer approval flow **cannot coexist**.
- **Fix:** namespace the callbacks (`approve_opt_<vid>` / `approve_reel_<id>`) or give the optimizer its own poll state + regex. Never reuse `post_row_id`-shaped callbacks for a different id space.

### A2 ✅ FIXED [C] `mark_posted("PENDING_MANUAL")` crashes on the 2nd manual post ever (UNIQUE collision), leaving Excel/DB inconsistent
**`src/core/data_store.py:37` (`post_id TEXT UNIQUE`), `data_store.py:171-182` (no `except`), `pipeline.py:776,1190`.**
Manual mode writes the literal `"PENDING_MANUAL"` into the UNIQUE `post_id` column; nothing reconciles it to a real IG id.
- **Failure scenario:** Day 1 `--manual` → row A `post_id='PENDING_MANUAL'` (ok). Day 2 `--manual` → `UPDATE posts SET post_id='PENDING_MANUAL'` → `sqlite3.IntegrityError: UNIQUE constraint failed` → uncaught → crash. At line 1190 it crashes **after** the Telegram video was sent (1170) and the Excel row marked (1189) → inconsistent state. Reproduces reliably on the 2nd manual post (state persists via the committed DB).
- **Fix:** don't reuse a UNIQUE sentinel — leave `post_id` NULL + a `status` column, or `f"PENDING_MANUAL_{row_id}"`, or catch `IntegrityError`.

### A3 ✅ FIXED [C] Ten "tests" can never fail — they swallow `AssertionError` and `return bool`
**`tests/test_phase1_integration.py` (test_imports L20/23, test_pattern_interrupt L45/47, test_brand_design L63/65, test_comment_bait L90/92, test_prompt_architect L121/123, test_wallpaper_composer L151/153, test_pipeline_integration L186/188); `tests/test_phase2_integration.py` (test_motion_engine L36/39, test_particle_overlay L68/71, test_light_ray_overlay L92/94).**
Every body is `try: … return True / except Exception: return False`. Pytest ignores the return, the bare `except` eats the `AssertionError` → a real regression becomes `return False` and the test still **PASSES**. No `filterwarnings=error` config exists. ~10 of the "517 passing" are decorative.
- **Fix:** delete the `try/except`+`return`; let asserts propagate. Add `filterwarnings = error::pytest.PytestReturnNotNoneWarning` to a `pytest.ini`.

### A4 ✅ FIXED [C/H — security] The live Meta token is written into the git-tracked `data/pipeline.db` by the code itself (cross-confirmed by two reviewers)
**`.gitignore` (`!data/pipeline.db` → tracked); `data_store.py:119-127` (`init_db` seeds `token_state.meta` from `META_ACCESS_TOKEN`), `data_store.py:298-316` (`save_token`), `token_manager.py:84,90`.**
Any run — **including `--dry-run`** — persists the 60-day token into the tracked file. Safeguards are all out-of-band: CI `DELETE FROM token_state` scrub, the `test_committed_db_has_no_token` guard, and manual `git checkout -- data/pipeline.db`. Currently clean (0 rows), but one local run + a natural `git add data/pipeline.db` (the workflow force-adds it) leaks the token. No in-process scrubbing.
- **Fix:** stop tracking `token_state` in the committed DB — ignored sidecar DB or external secret store, or scrub in `init_db`/`atexit`. Broaden `test_committed_db_has_no_token` (it only counts `token_state` rows; a token cached elsewhere would pass).

---

## B. Architecture Issues

### B1 ✅ MOSTLY FIXED [H] The optimizer's champion-challenger A/B is non-functional scaffolding
**`src/optimizer/experiments.py:evaluate` and `src/optimizer/reward.py:reward` have zero production callers** (grep: tests only). **`posts.opt_versions_json` is never added**, so no per-post reward attribution exists. The loop `open_experiment`s but nothing collects per-arm rewards or calls `evaluate`; the only closer is a human Telegram tap (`apply_decision`). The spec's "auto-upgrades to real IG A/B" is aspirational. Phase 1 delivers *critic proposals*, not *validated A/B*.
- **Fix:** implement attribution + a nightly `evaluate` pass (real Phase 1.5), or relabel experiments "human-judged" and drop the A/B claim until the data path exists.

### B2 ✅ FIXED [H] Open experiments never expire → an ignored proposal permanently stalls that asset
**`src/optimizer/loop.py:21` (`if get_open_experiment(key): continue`).** The only closers are `apply_decision` and the never-called `evaluate`. Ignore a proposal → its experiment stays `open` forever → that prompt asset never gets another proposal. Ignore all 5 → the loop is permanently inert while reporting success.
- **Fix:** expire open experiments after N days (reopen the asset); cap concurrent open experiments with a TTL.

### B3 [M] Approving a `copywriter`/`trend_scout` improvement is a silent no-op
**`src/optimizer/assets.py:10-14` registers 5 prompts, but only `studio/strategist.py` loads via `prompt_store.get`.** `copywriter._DRAFT_ROLE/_REVISE_ROLE` and `trend_scout._ROLE` are still static at their call sites. The loop proposes rewrites for them, you approve, the champion flips in the registry — and generation keeps using the old text. The system reports "improved" while changing nothing.
- **Fix:** finish the runtime wiring (mirror the strategist edit) before advertising them, or drop them from `MANAGED_PROMPTS` until wired.

### B4 [M] Predictive scoring engine is dead — and the optimizer inherited its orphaned weights
**`src/video/predictive_scoring.py`:** `compute_content_score` (`:92`) and `save_prediction` (`:203`) have no callers; the `predictions` table is never populated; `get_prediction_accuracy` (`:232`) always returns `insufficient_data`, so `weekly_brief.py:152-160`'s accuracy section is permanently dead. `FEATURE_WEIGHTS` are hand-set and never learned. `src/optimizer/reward.py` then hardcodes its own copy of the weights — a 6th duplicate (F1) of a formula whose original consumer doesn't run.
- **Fix:** wire predictive scoring into the pre-publish path or delete it; have `reward.py` import canonical weights rather than copy them.

### B5 [M] Failed publish permanently burns the day's slot (claim-before-publish)
**`pipeline.py:998,741` claim the slot via `save_post` before the un-try/excepted publish calls (`1195/1209/1222/779`); `has_posted_today` (`data_store.py:254-271`) blocks on any `dry_run=0` row even with `post_id=NULL`; `_wait_for_container` default `max_wait=60` (`instagram_poster.py:119-147`) raises `TimeoutError`.** A Reel container >60s (common) or any Meta 4xx crashes after the slot is claimed → `has_posted_today` True all day → no post, no retry.
- **Fix:** claim-on-success (publish first), or on failure delete/flag the claimed row; raise Reel `max_wait` to 120s+.

---

## C. Security Concerns

Overall posture is **solid**: no hardcoded secrets in tracked source, correct GitHub Actions `secrets.*` usage, `.env` properly ignored, no `pickle`/`yaml.load`/`eval`/`exec`/`shell=True` on external input.

- **C1 [H]** Live Meta token can leak via the tracked DB — see **A4** (the one real security issue).
- **C2 [L]** `test_committed_db_has_no_token` (`tests/test_workflow_reliability.py:38`) only asserts `count(*) FROM token_state == 0` — coupled to the "sole token writer" invariant. Broaden to scan all TEXT columns for token-shaped values.
- **C3 [info]** f-string DDL at `predictive_scoring.py:310` and `registry.py:19` `executescript` use only hardcoded literals — safe. `_sanitize_url`+`_retry_request` (`instagram_poster.py:18-54`) correctly prevent token leaks in HTTP error logs.

---

## D. Test Quality Problems

- **D1 [C]** 10 self-passing tests — see **A3**.
- **D2 [M]** Real-ffmpeg tests, no mock: `tests/test_reel_composer.py` `test_generate_reel_success` (L42), `test_generate_reel_silent_fallback` (L69), `test_ffmpeg_available` (L9) shell out to real ffmpeg and assert on real `.mp4` size — slow, fail on hosts without ffmpeg. **Fix:** `@pytest.mark.skipif(not ffmpeg_available())` or mock `subprocess.run` (as `test_pov_reel_generator.py:98` does).
- **D3 [M]** Untested prod publish paths: `post_to_instagram` (image, `instagram_poster.py:235`) and `post_carousel_to_instagram` (`:314`) have zero coverage — only the Reel path has a contract test. **Fix:** add contract tests mirroring `test_publish_contract.py`.
- **D4 [M]** Optimizer A/B code (`experiments.evaluate`, `reward.reward`) is exercised only by unit tests feeding synthetic reward lists; no integration test proves the loop ever produces them (it can't yet — B1). The green board overstates how much of the loop is wired.

---

## E. Performance & Cost

- **E1 [H]** Daily spend ceiling is a paper wall. `studio/run.py:17` checks `over_daily_ceiling()` once at t=0; the run then fires up to 4 opus calls unchecked, and `music_director`/`trend_scout` (`pipeline.py:557,611`) call `client.call` with **no ceiling check at all**. At `DAILY_SPEND_CEILING_USD=2.0`, one opus chain (`max_tokens=8000`, effort `high`, out=$25/1M) can blow past the cap. **Fix:** re-check the ceiling inside `StudioClient.call()` — the single chokepoint all calls share.
- **E2 [H]** `director.review` re-scores all N concepts with opus after a single-concept revision (`studio/director.py:37-47`) → 3 opus calls for the director stage on a revision, atop the opus copywriter draft. `copywriter`+`director` both opus+high (`settings.py:11-12,28-29`) is the largest, weakest-justified cost driver. **Fix:** `director`→sonnet (rubric scoring isn't opus-tier); skip post-revision re-score.
- **E3 [M]** Optimizer critic runs **5 opus/high calls every night** (`prompt_critic` = opus-4-8/high) across all managed prompts regardless of change, and keeps proposing against an already-good champion forever (no "good enough" stop). **Fix:** weekly cadence, cap proposals/asset, and/or sonnet critic.
- **E4 [M]** `prompt_store.get` calls `register_asset`→`init_optimizer_db` (3× `CREATE TABLE IF NOT EXISTS`) on **every call**, on the per-post hot path (`make_brief`→`build_role`→`get`). **Fix:** init once at startup; make `get` a pure read with a seed cache.
- **E5 [M]** Spend accounting ignores cache-token fields (`client.py:82-85`) → cached reads billed at full input rate, 1.25× cache-write premium ignored → ceiling math ≠ invoice.

---

## F. Dead Code & Duplication

- **F1 [H]** The composite engagement-score `saved*3.0 + comments*2.0 + reach*0.0015 + shares*2.5` is copy-pasted in **six** places: `cohort_analysis.py:308,348,395,405`, `predictive_scoring.py:80,244`, and now `src/optimizer/reward.py:6-9`. Change the weights once → predictions, cohorts, and optimizer reward silently desync. **Fix:** one canonical `SCORE_WEIGHTS` + shared SQL fragment.
- **F2 [M]** No dedup against rejected optimizer candidates (`src/optimizer/loop.py`): after a reject, `run_once` re-proposes the asset next night and nothing remembers rejected text → the critic can re-propose a rejected idea nightly forever. **Fix:** hash rejected candidates per key and skip.
- **F3 [L]** Dead code: unreachable haiku branch (`client.py:46-53`); unused `TextBlock` import (`client.py:48`) and `subprocess` import (`notifier.py:16`); dead `flux_override` assignments (`pipeline.py:852,879` overwritten at `910`); unreachable `if not parts` (`pipeline.py:401-403`); dead `caption_marker` hook-stamp (`pipeline.py:449`, overwritten at `1020`).

---

## G. Documentation Gaps & Correctness-of-claims

- **G1 [H]** Spec `2026-07-14-self-improving-loop-design.md` §5 claims the loop "auto-upgrades to real IG A/B … no code change." Reality: no attribution column, no `evaluate` caller (B1). **Fix:** annotate as Phase-1.5-pending.
- **G2 [M]** `--batch` silently drops `--seed` and `--content` (`pipeline.py:1296-1298` calls `generate_batch()` with no args) — documented flags dead in batch mode.
- **G3 [M]** `--content` with `row_number: null` (documented) + `--reel` (non-POV) crashes: `pipeline.py:1100,1133` call `_pick_cta(quote_data["row_number"])` → `_CTA_VARIANTS[None % len]` → `TypeError`. POV path guards it (`... or 0` at `:638`); FLUX path doesn't. **Fix:** `quote_data.get("row_number") or 0` at 1100/1133.
- **G4 [M]** Slot in **local** time (`excel_reader._current_slot` → `datetime.now().hour`) vs dedup in **UTC** (`date('now')`, `utcnow()`). CI (UTC) safe; local/other-tz can double-post or wrongly block near boundaries. **Fix:** same clock for slot and date.

---

## H. Top 10 Recommendations (ranked by impact)

1. **Namespace the Telegram callbacks (A1).** Today `optimize.py --apply-decisions` can promote the wrong prompt from a reel approval or silently eat reel approvals. `approve_opt_<vid>` vs `approve_reel_<id>` + separate poll state. *(~1h)*
2. **Fix `PENDING_MANUAL` UNIQUE crash (A2).** Manual mode is broken on its 2nd use. NULL `post_id` + `status` column. *(~1h)*
3. **Get the Meta token out of the tracked DB (A4/C1).** One careless `git add` leaks a live token. *(~2h)*
4. **De-fang the 10 fake-passing tests (A3/D1)** + add `filterwarnings=error`. The green board isn't trustworthy until this lands. *(~1h)*
5. **Enforce the spend ceiling inside `StudioClient.call` (E1)** + `director`→sonnet & skip post-revision re-score (E2). Biggest cost lever. *(~2h)*
6. **Decide the optimizer A/B story (B1+B2+G1):** wire `opt_versions_json` + nightly `evaluate` + experiment TTL, or relabel "human-judged" and add TTL so the loop can't stall. *(~4h real / ~1h relabel)*
7. **Finish or unregister copywriter/trend_scout wiring (B3).** Their approvals are silent no-ops today. *(~1h)*
8. **Move the optimizer cron off 08:00 UTC + serialize DB-committing workflows.** `daily_post` and `analytics` both push binary `pipeline.db` at 08:00 with no rebase → non-fast-forward push race + lost writes. Add a `concurrency` group and `git pull --rebase`. *(~1h)*
9. **Claim-on-success for slots (B5)** + raise Reel container timeout to 120s. Stops one publish failure from silently burning a day. *(~2h)*
10. **Collapse the 6 copies of the score weights into one constant (F1)**; then decide predictive scoring lives (wire it) or dies (delete it) (B4). *(~2h)*

---

### Cross-checked NON-issues (don't chase)
- All `studio/types.py` schemas set `additionalProperties: False` via `_obj` — compliant. (The optimizer's `CRITIC_SCHEMA` was the sole offender; already fixed + regression-tested.)
- `music_director.select_music` honors its never-raises contract (internal catches in `jamendo_music.py`).
- No `KeyError` for live studio roles — all registered in `ROLE_MODELS`/`ROLE_EFFORT` (incl. the new `prompt_critic`).
- Predictive scoring has no div-by-zero/cold-start crash — it's dead (B4), not crashing.
- Atomic `save_post` `ON CONFLICT DO NOTHING` dedup is sound; token-refresh paths are well tested; receipt upload has path-traversal validation.
