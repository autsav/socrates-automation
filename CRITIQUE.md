# Critique — 2026-07-11

Scope: full read of `pipeline.py`, `config.py`, `studio/*`, `team/orchestrator.py`, `src/core/*`, `.github/workflows/*`, plus targeted greps across the tracked tree (224 files). Findings below are verified against source; line numbers are from the files as they stand today. Where a finding depends on runtime behavior I could not execute (local Python is 3.9; repo needs 3.11), it is marked *(static)*.

---

## A. Critical Bugs (must fix before production)

### A1. `analytics.yml` DB-commit step is broken — `git add` on a gitignored path errors
- **File:** `.github/workflows/analytics.yml`, step "Commit SQLite database back to repo".
- **What:** Runs `git add data/pipeline.db` (no `-f`). `data/` **and** `*.db` are both in `.gitignore` (verified: `git check-ignore data/pipeline.db` → matches). `git add` of an explicitly-named ignored path exits non-zero with "The following paths are ignored…", failing the step. The sibling workflow `daily_post.yml` does this correctly with `git add -f data/pipeline.db logs/`.
- **Why it matters:** The analytics job's whole purpose is to fetch metrics and persist them back to the repo DB. This step never succeeds, so ingested metrics/A-B results are discarded — the A/B optimizer and analyst never see real numbers.
- **Fix:** Change to `git add -f data/pipeline.db` (and guard with `git diff --staged --quiet || git commit …` as daily_post does).

### A2. SQLite state is effectively ephemeral in CI → dedup guard and A/B learning reset every run
- **Files:** `.github/workflows/daily_post.yml` (steps "Init SQLite database", "Restore SQLite database from repo", "Commit …"); `src/core/data_store.py:12`.
- **What:** `data/pipeline.db` is **not tracked** (`git ls-files data/pipeline.db` → empty) and is gitignored. `actions/checkout` therefore restores nothing; the "Init" step calls `init_db()` creating a fresh empty DB; the "Restore" step only checks file existence (always true after Init) so it is a no-op. Persistence depends entirely on the final `git push`, which the workflow's own comment admits may 403 ("GITHUB_TOKEN may not have write access"). If that push ever fails, every subsequent run starts from an empty DB.
- **Why it matters:** `has_posted_today(slot)` (`data_store.py:225`) returns False on an empty DB, defeating the duplicate-post guard; `ab_results`/`token_state`/`proposals` all reset, so A/B bandit (`src/analytics/ab_test.py`) and studio reconcile lose history.
- **Fix:** Commit an initial `data/pipeline.db` into the repo (force-add once), verify the push has write perms (`permissions: contents: write` in the workflow), and make "Restore" fail loudly if the DB is missing rather than silently continuing on a fresh one.

### A3. TOCTOU on the "already posted today" guard
- **File:** `pipeline.py:552-555` (`has_posted_today`) then `save_post` at `:687` / `:460`; `src/core/data_store.py:225-242`.
- **What:** The check-then-insert is not atomic and there is no unique constraint on `(date(posted_at), posting_slot, dry_run=FALSE)`. Two overlapping runs for the same slot (e.g. a manual `workflow_dispatch` firing near a cron) both pass the guard and both post.
- **Why it matters:** Double-posting the same slot to Instagram is user-visible and can trip spam heuristics.
- **Fix:** Add a UNIQUE index on the slot/day and rely on `INSERT … ON CONFLICT` to make the guard atomic, or take an OS file lock around the read-post-write section.

### A4. Token refresh fires a network POST on every run and can never stop
- **File:** `src/core/token_manager.py:13-21, 34-36, 63-86`; seed at `src/core/data_store.py:101-108`.
- **What:** `init_db` seeds the `meta` token with `expires_at = NULL`. `_is_token_expiring_soon(None)` returns True, so `refresh_if_needed` always attempts a refresh. A new 60-day `expires_at` is only saved **when the token value changes** (`token_manager.py:79`). If `META_APP_ID`/`META_APP_SECRET` are unset (they are optional, `config.py:40-41`) the refresh POST fails, the same token is returned, `expires_at` stays NULL forever → a wasted, failing Graph API call on **every** pipeline invocation (6+/day).
- **Why it matters:** Silent, permanent failure path plus needless latency/rate-limit exposure; the "auto-refresh" feature is effectively inert.
- **Fix:** Persist an `expires_at` even when the token is unchanged (best-effort estimate), and skip the refresh path entirely when app id/secret are absent.

### A5. `--studio --manual` never publishes — "automation" ends at a Telegram nudge
- **File:** `pipeline.py:839-865`; `.github/workflows/daily_post.yml` scheduled branch runs `python pipeline.py --studio --manual`.
- **What:** In `manual=True` mode the pipeline generates the asset, sends it to Telegram, marks the row `PENDING_MANUAL`, and **returns without calling the Graph API**. The only auto-publishing paths (`post_reel_to_instagram`, `post_carousel_to_instagram`, `post_to_instagram`) are gated behind `elif not dry_run:` which manual mode skips.
- **Why it matters:** This may be intentional (human adds trending audio), but it is undocumented as the *default production behavior*: `src/core/instagram_poster.py` is never exercised by the scheduled cron, so its publish path is effectively untested in production. Anyone reading the repo will assume it posts automatically.
- **Fix:** Document this explicitly at the top of `pipeline.py`/README, and add a fully-automated cron variant (or a CI smoke test) that exercises the real Graph API publish path so it does not rot.

### A6. Reconcile matches on a caption marker that may not be present in the posted caption
- **File:** `studio/reconcile.py:24-32, 35-40`; producer at `pipeline.py:380` (`caption_marker = concept.hook`) and caption assembly at `pipeline.py:584-591`.
- **What:** Reconcile backfills the real `post_id` by substring-matching `visual_direction.caption_marker` (the studio hook) inside the fetched Instagram caption. But the caption actually sent is `concept.caption` + a CommentBait engagement block (`pipeline.py:591`); the hook string is not guaranteed to appear verbatim in `concept.caption`. If the human edits the caption before posting (the whole point of manual mode), the match fails silently (`match` returns None).
- **Why it matters:** Unreconciled proposals never get a `post_id`, so `metrics.py` can never fetch their performance — the analytics feedback loop silently drops manual posts.
- **Fix:** Match on a stable invisible token (e.g. a zero-width marker or a short hashtag appended to every caption), or reconcile by timestamp proximity + audience rather than fragile substring.

---

## B. Architecture Issues

### B1. Three parallel content systems, only one wired to production
- **Files:** legacy `pipeline.py` + `src/*`; `studio/*` (4 agents); `team/*` (9 agents).
- **What:** Production CI (`daily_post.yml`) only ever calls `pipeline.py`. `studio/` is bolted on via `--studio` with legacy fallback. `team/` (`orchestrator.py`, 9-agent debate → JSON in `team/output/`) is **never imported outside `team/` and `tests/`** (verified: `grep -rn "run_team_pipeline|team.orchestrator|team.live|team.dashboard"` outside tests → no matches; `team` absent from every workflow). It writes JSON artifacts nothing consumes and never posts.
- **Why it matters:** ~15 `team/*` modules + 9 prompt files + ~15 test files are maintained but dead in production; `team/` even imports `studio.client.StudioClient` (`team/orchestrator.py:26`), so `studio/` has silently become shared infra for two unconnected orchestrators. This is a large ongoing maintenance/cost tax on code that produces nothing.
- **Fix:** Either wire `team/` output into `pipeline.py` posting, or move it to an `experiments/` folder excluded from CI, or delete it. Decide and document which system is canonical.

### B2. `backend/` (FastAPI receipt upload) is an unrelated product in the same repo
- **Files:** `backend/main.py`, `backend/app/routers/receipts.py`, `backend/app/supabase_client.py`, `vercel.json`.
- **What:** A Supabase-backed receipt-upload microservice with no code path connecting it to the Instagram pipeline. It shares the repo, the `.env`, `requirements.txt`, and CI checkout.
- **Why it matters:** Couples unrelated deploy/secret surfaces (Supabase service key sits in the same `.env` as Meta/Cloudinary keys), bloats `requirements.txt` (fastapi/uvicorn/supabase/pydantic pulled into the Instagram CI image), and confuses ownership.
- **Fix:** Split into its own repo, or at minimum isolate its dependencies (separate requirements file) and secrets.

### B3. Duplicated content pools between `pipeline.py` and the agents
- **Files:** `pipeline.py:96-211` (`_PSYCHOLOGY_HOOKS`, `_CONTROVERSY_QUESTIONS`, `_CTA_VARIANTS`, `_HASHTAG_POOL`) vs. the same responsibilities inside `team/content_writer.py` / `team/engagement_strategist.py` and `src/engagement/comment_bait.py`.
- **What:** Hook/CTA/controversy/hashtag generation exists as hardcoded dict pools in `pipeline.py`, again as LLM agents in `team/`, and again in `src/engagement/comment_bait.py` (which `pipeline.py:584` also invokes on top of its own pools).
- **Why it matters:** The same post gets a viral-first-line + emoji + CTA from `_enhance_caption`, then a *second* CTA/question block from CommentBait (`pipeline.py:591`) — captions accrete redundant CTAs. Three sources of truth for the same content dimension.
- **Fix:** Consolidate caption assembly into one module; have `pipeline.py` call it once rather than layering `_enhance_caption` + CommentBait.

### B4. `_build_pool` is shared across studio and team but lives in `studio/run.py`
- **Files:** `studio/run.py:33-48`, imported by `team/orchestrator.py:27` and `pipeline.py:396`.
- **What:** The quotes.xlsx reader is a private `_build_pool` in `studio/run.py` reused by two other systems, creating an implicit cross-package dependency on a name marked private.
- **Fix:** Promote to `src/core/excel_reader.py` (which already owns Excel access) as a public function.

### B5. Dead / redundant assignments and layering in `run_pipeline`
- **File:** `pipeline.py:559, 600`.
- **What:** `flux_override = ""` is set at `:559`, then unconditionally reset to `""` at `:600` before being recomputed — the first assignment is dead. The studio-vs-legacy branching for `flux_override`/`mood`/`controversy` is duplicated across `:560-581` and `:599-610`.
- **Fix:** Collapse the two flux_override blocks; remove the dead assignment.

---

## C. Security Concerns

### C1. Sensitive/generated files committed despite `.gitignore`
- **Files (tracked):** `logs/posts.jsonl`, `server.log`, `output/*.jpg` (18 images), `audio/*.mp3` (7), plus `.DS_Store`, `docs/.DS_Store`, `docs/superpowers/.DS_Store`.
- **What:** `.gitignore` lists `output/`, `logs/`, `*.mp3`, `server.log`, `.DS_Store` — but these were committed before the ignore rules and remain tracked (gitignore does not retroactively untrack). `logs/posts.jsonl` contains full post history (quotes, captions, audiences, absolute local paths exposing the username `/Users/utsab1/…`).
- **Why it matters:** Leaks local filesystem layout and operational history; `.DS_Store` can leak directory listings; repo bloat.
- **Fix:** `git rm --cached` all of the above, commit, confirm they stay ignored. Scrub absolute paths from `posts.jsonl` (store relative paths only — see `pipeline.py:945` which already writes absolute paths in newer records).

### C2. `.env` handling is correct — verify it stays that way
- **What:** `.env` is present on disk but **not tracked** (`git ls-files | grep -E "\.env$"` → empty), and `.env.example` contains only placeholders (`your_*_here`). Good.
- **Residual risk:** The Supabase **service-role** key (`SUPABASE_SERVICE_KEY`, `.env.example:47`) sits in the same `.env` as all social keys (see B2) — a service-role key bypasses row-level security. Blast radius of any `.env` leak is maximal.
- **Fix:** Isolate backend secrets; prefer an anon key + RLS for the receipts service if possible.

### C3. Backend receipt-upload endpoint — review auth/authz *(static — confirm against `backend/app/routers/receipts.py`)*
- **What:** A public upload endpoint backed by a Supabase service-role client is a classic unauthenticated-write / path-traversal / content-type-spoofing surface. This warrants explicit checks: is there any auth on the POST? Is the filename user-controlled and used in the storage path? Is upload size/type bounded?
- **Why it matters:** Service-role + unauthenticated upload = anyone can write to your bucket.
- **Fix:** Require auth (signed URL or bearer), sanitize/whitelist filenames and content types, cap size, and downgrade to the least-privileged key.

### C4. `trending_music.yml` interpolates unsanitized data into a shell `curl`
- **File:** `.github/workflows/trending_music.yml` (reminder step) — `MESSAGE` includes `${{ steps.check.outputs.last_update }}` parsed via `grep -oP` from `src/audio/trending_music.py`, then passed to `curl -d "text=$MESSAGE"`.
- **What:** The value comes from a source file the workflow greps; if that file's `"updated"` field ever contained shell/URL-special characters it is injected unescaped into the curl body. Low severity (source is repo-controlled) but a real injection shape.
- **Fix:** Pass via `--data-urlencode` and quote defensively.

### C5. No unsafe deserialization / eval found (positive)
- **What:** No `pickle.load`, `yaml.load` without SafeLoader, `eval(`, `exec(`, `os.system`, or `subprocess(..., shell=True)` in tracked source (grep clean). Studio JSON parsing uses `json.loads` on model output with try/except (`studio/client.py:76-79`). Good.

---

## D. Test Quality Problems

*(Static analysis; suite runs only under the 3.11 `.venv`.)*

### D1. Broad swallowed-exception census in production code (not tests, but undermines test signal)
- **Files/lines:** `except Exception: pass` at `src/audio/download_music.py:73, 149, 194`; `src/audio/trending_audio.py:150`; `src/audio/trending_hijacker.py:99, 198, 206`; `src/core/notifier.py:576, 659, 702, 789`; `src/engagement/auto_reply.py:69`. Broad `except Exception:` (no re-raise/log) at `src/prompts/architect.py:318`, `src/visual/brand_design.py:157/164/183`, `src/video/reel_composer.py:82/106/115`, `src/video/beat_sync.py:119`, `src/video/predictive_scoring.py:311`, `src/hooks/pattern_interrupt.py:295`, `src/visual/image_composer.py:66`, `src/video/pov_reel_generator.py:237/245/253`.
- **What:** Bare `pass` handlers hide the failure mode entirely; tests exercising these paths will "pass" even when the underlying operation silently no-ops.
- **Why it matters:** Green tests do not imply working behavior — e.g. a music download that always fails is indistinguishable from success.
- **Fix:** Replace `pass` with `log.warning(..., exc_info=True)`; narrow the exception types; assert on observable outputs in tests, not on "no exception raised."

### D2. Non-blocking `try/except` around every pipeline side-effect masks regressions
- **File:** `pipeline.py:629-640, 668-683, 790-803, 913-924, 929-935`.
- **What:** Overlays, wallpapers, voiceover, notification, and `save_proposal` are each wrapped in `try/except … log.warning(non-blocking)`. A test that runs `run_pipeline` end-to-end will pass even if all five features are broken.
- **Fix:** In tests, assert each artifact was produced (mock the collaborators and assert calls), rather than trusting the pipeline's return record.

### D3. Confirm tests assert rather than swallow *(hand off to test-quality agent's line list)*
- **What:** The dedicated test-quality pass targeted tests that `try/except: return True` or lack any `assert`/`assert_called`/`pytest.raises`. Given ~55 test files (including ~15 for the dead `team/` system, B1), the highest-value action is verifying the *live* paths (`pipeline.py`, `studio/*`, `src/core/*`, `src/visual/image_composer.py`) have real assertions and that the manual/Graph-API publish path (A5) is covered at all.
- **Fix:** Grep the suite for `return True`/`return False` inside `except` blocks and for test bodies with zero `assert`; convert to explicit assertions.

### D4. `data/pipeline.db` schema drift risk untested
- **File:** `src/core/data_store.py:45-49` (runtime `ALTER TABLE` migration for `hook_id`), plus `CREATE TABLE IF NOT EXISTS` scattered inside `save_engagement_pod_member`/`get_engagement_pod`/contest functions (`:482, 503, 521, 547`).
- **What:** Migrations happen implicitly at call time; no test asserts an old DB upgrades cleanly.
- **Fix:** Add a migration test that opens a pre-`hook_id` DB fixture and asserts `init_db()` upgrades it.

---

## E. Performance & Cost

### E1. Reel mode calls Fal.ai FLUX three times per post
- **File:** `pipeline.py:711-736`.
- **What:** Generates three separate backgrounds (hook/quote/CTA scenes), each a full FLUX call (~£0.003 each per the header, `pipeline.py:5`), on top of the initial background at `:618`. That is 4 FLUX calls per reel post, ×3 reel slots/day.
- **Why it matters:** ~4× the image cost the header advertises ("£0.17/month" is optimistic given reels + carousels).
- **Fix:** Generate one background and derive scene variants via crops/overlays (the code already has `src/overlays/particles.py` and Ken Burns), or reuse a single FLUX image across all three scenes.

### E2. Studio uses Opus for copywriter + director on every slot
- **File:** `studio/settings.py:8-35`; `studio/client.py:14-18`.
- **What:** `copywriter` and `director` (and team's `content_writer`) are pinned to `claude-opus-4-8` at `effort: high`, drafting `N_CONCEPTS = 4` (`settings.py:36`) concepts per run. Opus is priced at $5/$25 per 1M (`client.py:16`) vs Haiku $1/$5. This runs on the scheduled cron (up to 6×/day) under a `DAILY_SPEND_CEILING_USD = 2.0` cap (`settings.py:37`).
- **Why it matters:** Two Opus/high calls per slot dominate spend and can hit the $2/day ceiling, at which point `run_studio` silently falls back to legacy templates (`studio/run.py:17-18`) — you pay premium prices early in the day and degrade later.
- **Fix:** Move copywriter to Sonnet (director stays Opus if quality demands), reduce `N_CONCEPTS`, and cache/deduplicate the analyst brief (already TTL-cached 24h — good, `settings.py:41`).

### E3. Redundant per-call `CREATE TABLE IF NOT EXISTS`
- **File:** `src/core/data_store.py:482, 503, 521, 547`.
- **What:** Pod/contest tables are (re)created on every read/write call instead of once in `init_db()`.
- **Why it matters:** Extra DDL round-trips on hot-ish paths; the tables are absent from `init_db` so their existence is order-dependent.
- **Fix:** Move these `CREATE TABLE` statements into `init_db()`.

### E4. Sequential-by-design team pipeline pays for 9 LLM agents to produce dead JSON
- **File:** `team/orchestrator.py` (whole module; B1).
- **What:** Nine LLM stages (analytics Haiku, then multiple Sonnet/Opus agents) run per invocation to write artifacts nothing posts.
- **Fix:** Do not run it in any paid context until it is wired to production (B1).

---

## F. Dead Code & Duplication

### F1. `team/` — dead in production (see B1)
- ~15 modules (`team/*.py`), 9 prompt files (`team/prompts/*.md`), ~15 test files. No live importer.

### F2. `socrates_pipeline/` — untracked on-disk duplicate of much of `src/`
- **What:** `socrates_pipeline/` exists on disk (contains `ab_test.py`, `analytics.py`, `beat_sync.py`, `carousel_composer.py`, `config.py`, `data_store.py`, `download_music.py`, …) and is gitignored (`.gitignore` "Nested repo"); `git ls-files socrates_pipeline` → 0 tracked. It is a stale duplicate of `src/` living beside the real one.
- **Why it matters:** Anyone editing the wrong copy loses work; grep/tooling gets confused.
- **Fix:** Delete the directory (it is not part of the repo).

### F3. Overlapping audio modules
- **Files:** `src/audio/trending_music.py`, `trending_audio.py`, `trending_hijacker.py`, `download_music.py`; and voiceover trio `voiceover.py`, `voiceover_engine.py`, `edge_tts_engine.py`.
- **What:** Four "trending audio" modules and three voiceover engines with overlapping responsibilities; `pipeline.py:771-823` cascades OpenAI TTS → legacy voiceover → edge-tts as three fallbacks.
- **Fix:** Collapse to one trending-audio provider interface and one voiceover interface with pluggable backends.

### F4. `motion_effects.py` — verify it is reachable
- **File:** `src/visual/motion_effects.py` (`MotionEngine`, `Easing`).
- **What:** A rich Ken-Burns/easing engine; `pipeline.py` does not import it directly (reel uses `src/video/reel_composer.py`). Confirm `reel_composer` actually calls `MotionEngine`; if not, this is dead. (The `Easing` enum itself is internally consistent — `Easing.EASE_OUT_EXPO` is correctly namespaced at `motion_effects.py:47`, so no NameError there.)
- **Fix:** Wire it into `reel_composer` or remove.

### F5. Dead assignment in `pipeline.py:559` (see B5).

---

## G. Documentation Gaps

### G1. No root README
- **What:** No `README*` at repo root. The only overview is `ANALYSIS.md` (a critique, not usage docs) and scattered `docs/*` strategy briefs.
- **Fix:** Add a README stating: which of the three systems is canonical (studio via `pipeline.py`), that scheduled runs are **manual-publish via Telegram** (A5), and the required secrets.

### G2. Header cost/architecture comment is stale
- **File:** `pipeline.py:1-12`.
- **What:** Advertises "Total ~£0.17/month" and a single-FLUX-image flow, but the live path adds studio Opus calls (E2), 3–4 FLUX calls per reel (E1), reels, carousels, wallpapers, and voiceover.
- **Fix:** Update the cost model and the data-flow comment to match reality (studio + manual + multi-asset).

### G3. `team/`'s ContentPlan schema-lock is undocumented at the seam
- **What:** `team/` `ContentPlan` is schema-locked to 7 posts/week, while production (`daily_post.yml`) posts 6/day + 2 carousels/week. These two cadences are incompatible and the mismatch is only discoverable by reading both. If `team/` is ever wired in (B1), this will break.
- **Fix:** Document the cadence contract and reconcile the schema before integrating.

### G4. Specs describe robustness features whose CI wiring is broken
- **Files:** `docs/superpowers/specs/2026-06-23-pipeline-robustness-design.md` vs A1/A2.
- **What:** Checkpoint/resume (`team/orchestrator.py`) and DB persistence are specced as robustness wins, but the analytics DB commit is broken (A1) and the DB is ephemeral (A2).
- **Fix:** Note the CI persistence caveat in the spec, or fix the workflows.

---

## H. Top 10 Recommendations (ranked by impact)

1. **Fix DB persistence in CI (A1 + A2).** Force-add an initial `data/pipeline.db`, add `permissions: contents: write`, use `git add -f` in `analytics.yml`. Without this, dedup, A/B learning, and analytics silently do nothing.
2. **Make the duplicate-post guard atomic (A3).** UNIQUE index on `(day, slot)` + `INSERT … ON CONFLICT`. Prevents double-posting to Instagram.
3. **Decide the fate of `team/` (B1/F1/E4).** Wire it to production or move it out of CI. It is the single largest block of dead, paid-to-run code.
4. **Untrack sensitive/generated files (C1).** `git rm --cached logs/posts.jsonl server.log output/*.jpg audio/*.mp3 **/.DS_Store`; scrub absolute local paths from `posts.jsonl`.
5. **Lock down / isolate the backend receipts service (C3/B2/C2).** Add auth + filename sanitization, split its deps and its Supabase service-role key out of the shared `.env`.
6. **Cut FLUX and Opus cost (E1/E2).** One FLUX background per reel instead of 3–4; move copywriter to Sonnet; the header's cost claim is off by an order of magnitude.
7. **Document that production is manual-publish (A5/G1/G2).** Add a README and fix the stale `pipeline.py` header so the Telegram-nudge behavior is not a surprise; add a smoke test for the real Graph API publish path.
8. **Make reconcile robust (A6).** Match manual posts by a stable token/timestamp, not fragile hook-substring matching, so analytics stops dropping manual posts.
9. **Fix the token-refresh dead loop (A4).** Persist `expires_at` even when unchanged and skip refresh when app id/secret are absent.
10. **Replace swallowed exceptions with logged failures (D1/D2).** Convert `except Exception: pass` to `log.warning(exc_info=True)` and narrow types, so broken subsystems stop hiding behind green pipelines/tests.

---

### Positives worth preserving
- Clean secret handling via `Config` (`config.py`) with a helpful GitHub-Actions error path; `.env` correctly untracked.
- SQLite access uses `try/finally` everywhere (no connection leaks) and WAL mode (`data_store.py`).
- Studio has a genuine spend ceiling + graceful legacy fallback (`studio/run.py`, `studio/client.py`).
- No unsafe deserialization / shell-injection in Python source (C5).
