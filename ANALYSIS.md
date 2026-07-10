# Socrates Automation — Full Project Analysis

Scope: full repo minus `.git/`, `.venv/`, `__pycache__/`, `socrates_pipeline/` (a legacy, untracked, on-disk-only duplicate of much of `src/` — see §J.10). This report was produced by reading every source file in `pipeline.py`, `config.py`, `studio/`, `team/`, `src/`, `backend/`, `tests/`, `.github/workflows/`, `docs/`, plus git history, `.gitignore` coverage, and a live `pytest` run.

---

## A. Architecture

Three generations of the same idea, coexisting in one repo:

1. **Legacy pipeline** (`pipeline.py` + `config.py` + `src/*`) — deterministic, template-driven content → image/reel → Instagram. Oldest, most battle-tested, most tested.
2. **AI Creative Studio** (`studio/*`) — 4-agent reasoning pipeline (analyst → strategist → copywriter → director) that uses Claude to pick concepts instead of templates. An optional layer bolted onto `pipeline.py` via `--studio`; falls back to the legacy path on failure.
3. **Team system** (`team/*`) — a separate, fuller 8-agent simulation (planner/reviewer debate + 6 specialist agents) with its own orchestrator, a live Flask/SSE dashboard, and JSON artifact output. **Not wired into `pipeline.py` at all** — a parallel, self-contained system invoked independently via `team/orchestrator.py` / `team/live.py`. It even imports `studio.client.StudioClient` for its own LLM calls, so `studio/` has effectively become shared infrastructure for two unconnected orchestrators.
4. **`backend/`** — a fourth, **fully unrelated** FastAPI receipt-upload micro-service (Supabase-backed), deployed separately to Vercel (`vercel.json`). Shares the repo, `.env` file, and CI checkout, but no code path connects it to the other three systems. Looks like a different product prototyped in the same repo.

Production data flow, per the actual scheduled workflow (`.github/workflows/daily_post.yml` always runs `pipeline.py --studio --manual`):

```
quotes.xlsx ──► pipeline.py --studio --manual
                  │
                  ├─ studio/run.py: analyst → strategist → copywriter → director
                  │     └─ on any StudioError / None → legacy template path
                  │        (src/content, src/analytics/ab_test)
                  ├─ src/engagement/comment_bait.py (caption engagement block)
                  ├─ src/prompts/architect.py or studio flux_prompt → FLUX prompt
                  ├─ src/visual/image_generator.py (Fal.ai FLUX) → background image
                  ├─ src/overlays/particles.py (optional, non-blocking)
                  ├─ src/visual/image_composer.py (Pillow composition)
                  ├─ src/wallpapers/composer.py (optional, non-blocking)
                  ├─ src/core/data_store.py (SQLite, persisted BEFORE publish)
                  ├─ [--reel] src/video/reel_composer.py (ffmpeg, beat-synced via src/video/beat_sync.py,
                  │           voiceover via src/audio/voiceover_engine.py → voiceover.py fallback)
                  └─ src/core/notifier.py → Telegram
                       (manual mode: no Graph API call — human posts by hand)
```

Key fact: because the scheduled CI job always pairs `--studio` with `--manual`, `src/core/instagram_poster.py` (the real Meta Graph API publisher) is exercised only in ad-hoc/manual invocations, not by the automated cron. **Today's "posting" pipeline actually ends at "send a proposal to Telegram" — a human does the real publish.** `studio/reconcile.py` runs later (via `analytics.yml`) to match that manually-published post back to a `proposals` row by substring-matching a caption marker.

---

## B. The Team System

8 agent classes in `team/*.py`, each a thin wrapper: load a markdown persona from `team/prompts/*.md` (via `team/prompt_loader.py`) → build a prompt with a module-level `build_prompt()` helper (kept separate from the class for testability without mocking the API) → call `StudioClient.call(role, ...)` (the real `studio/client.py`) → parse the JSON response into a `team/models.py` dataclass.

| Agent | Model/effort (`studio/settings.py`) | Output |
|---|---|---|
| Analytics Analyst | Haiku / (no thinking/effort — see §C) | `AnalyticsReport` |
| Planner | Sonnet / medium | `ContentPlan` (7-day) |
| Reviewer | Sonnet / medium | critique + score |
| Content Writer | **Opus / high** | `CopySpec` |
| Visual Designer | Sonnet / medium | `VisualSpec` (FLUX prompts) |
| Audio Engineer | Sonnet / medium | `AudioSpec` |
| Video Editor | Sonnet / medium | `VideoSpec` |
| Engagement Strategist | Sonnet / medium | `EngagementSpec` |

**Debate loop** (`team/debate.py:29-68`): a plain `while True` — planner drafts a plan, reviewer scores it, `approved = review["score"] >= approval_threshold` (8.0 by default; the reviewer's own self-reported `approved` flag is explicitly discarded in favor of this computed check — confirmed by a dedicated test). Loop exits on `approved or round_number == max_rounds` (default 3). This is **a single critic gating a single generator**, not a true multi-party debate/voting mechanism, and — critically — **there is no reject path**: if round 3 is reached without ever crossing the threshold, the (still-unapproved) plan is returned and used anyway.

**Orchestrator** (`team/orchestrator.py`): strictly, deliberately sequential — analytics → build quotes pool → debate → content writer → visual designer → audio engineer → video editor → engagement strategist → write 7 JSON files to `team/output/`. The module docstring explicitly forbids adding concurrency ("low-frequency batch job, not a hot path"). Every stage is wrapped by `_stage()`, which fires start/done/failed callbacks and **re-raises** any exception (no swallowing, no fallback path, no `over_daily_ceiling()` spend gate — unlike `studio/run.py`, which does check the ceiling before spending).

**Dashboard** (`team/dashboard.py` + `team/live.py`): a real **Flask + Server-Sent-Events** UI, not a mock — `EventBus` is a thread-safe pub/sub (`publish()`/`subscribe()` under a lock, late subscribers get full history replay before live streaming). `make_callbacks()` wires all 8 `on_*` orchestrator callbacks straight into `bus.publish()`. `team/live.py` runs the pipeline on a background daemon thread and serves Flask on the main thread. This is genuine, tested, working glue code — but it is glue for a subsystem that is itself disconnected from production (see below).

**Data models** (`team/models.py`): clean `@dataclass` + `to_dict`/`from_dict` pairs, 14 strict JSON schemas (`additionalProperties: false`). Gap: none of the schemas use `enum` constraints on closed-vocabulary fields (`mood`, `audience`, `format`, `hook_strategy`) even though the prompts insist these are a fixed, authoritative set — and the canonical `AUDIENCE_TO_MOOD`/`VALID_MOODS` mapping already exists in `src/core/excel_reader.py` but `team/` never imports or cross-checks against it. No `minItems`/`maxItems` on the "7 posts" arrays either.

**Confirmed bugs**:
- `dry_run` is threaded through the entire CLI/orchestrator/tests but **never read anywhere in the function body** — a complete no-op, and a test locks this in as expected behavior rather than flagging it.
- **Unapproved plans are silently reported and saved as "approved."** When round 3 is hit without crossing the score threshold, `orchestrator.py`'s stage summary still hard-codes `"Plan approved after N round(s)..."`, the deliverable event says `"7-day plan approved..."`, the variable is literally named `approved_plan`, and the output file is `approved_plan_{date}.json` — regardless of the reviewer's actual verdict. Five more paid LLM calls (content writer through engagement strategist) then proceed to build on a plan the reviewer explicitly rejected. Zero tests exercise this path — both test fixtures that construct `DebateResult` hardcode `approved=True`.
- `_build_pool("quotes.xlsx")` runs between two `_stage()`-wrapped calls, not inside one — if it throws (missing/corrupt Excel file), there is no `stage_failed` event, just a generic unattributed `pipeline_failed` event, leaving the dashboard's remaining stage indicators stuck gray with no signal of what broke.
- `team/live.py` and `team/prompt_loader.py` have zero test coverage.

**`team/` is invoked by nothing in production** — no cron job, no workflow, no other module imports it. It is fully built, well-tested (the debate/orchestrator/dashboard tests are the strongest in the whole repo — real dependency-order assertions, `ast`-based static checks that it never imports `pipeline`, full event-sequence integration tests), but functionally an orphaned parallel system.

---

## C. The Studio System

`studio/client.py` — thin wrapper over the `anthropic` SDK. Per-role model dispatch (`studio/settings.py`): non-Haiku roles get `thinking={"type":"adaptive"}` + forced `output_config.json_schema` structured output + prompt caching (`cache_control: ephemeral` on the shared prefix). **The Haiku branch (`is_haiku = "haiku" in model`) drops `thinking` and `output_config` entirely** and instead appends the schema as plain text to the system prompt with a "return ONLY valid JSON" instruction — correct fix for Haiku's lack of thinking/effort support (recent commit `1db9a8c`, verified correctly implemented), but it also means Haiku gets **prompt-only** JSON compliance, not real schema-enforced structured output, and it collapses the system prompt into one uncached block rather than reusing the shared-prefix cache path. This exact branch has no dedicated test asserting Haiku's call kwargs specifically lack `thinking`/`output_config`.

Response parsing (`client.py:56-79`, recent commit `6195971`) is now genuinely robust: checks `stop_reason == "refusal"` first, skips thinking blocks while scanning for a text block, falls back to `resp.output_text`, raises a descriptive `StudioError` on an empty result, and strips markdown code fences. **Correctly implemented and a real improvement.** One residual gap: it only strips a fence that is the very first/last thing in the string — prose before a ` ```json ` fence (e.g. `"Here's the JSON:\n```json\n{...}\n```"`) isn't stripped, but this degrades to a safe `StudioError`, not a crash or a silently-wrong parse.

**Chain**: `studio/run.py:run_studio()` — checks `client.over_daily_ceiling()` first → Analyst (`get_or_build_brief`, a cached 24h-TTL `PerformanceBrief`, reused stale-on-failure) → Strategist (`CreativeBrief`) → Copywriter (4 `Concept`s) → Director (scores, at most one revision round-trip back to the copywriter) → returns `(brief, decision, concept_map)`. Any `StudioError` anywhere → logged, returns `None`, the documented fallback-to-legacy signal.

### Critical bug: the strategist's prompt contradicts its own enforced schema

`studio/strategist.py` instructs the model to set `quote` to either `{"row_number": N, "text": "..."}` or `{"need_new": true, "theme": "..."}` — but `studio/types.py`'s `CREATIVE_BRIEF_SCHEMA` defines `quote` as a **strict** `{"text", "author", "source"}` object with `additionalProperties: false`. Neither `row_number` nor `need_new`/`theme` is a legal key under the enforced schema. Root cause confirmed via `git show 8a84e65` ("add explicit additionalProperties:false to all JSON schemas") — that commit tightened `types.py`'s schema but never touched `strategist.py`'s prompt text, so prompt and schema have been silently contradicting each other since.

Effect: because Anthropic's structured output enforces the schema, the model can **never** legally emit `row_number`. `pipeline.py:_apply_studio_decision` reads `brief.quote.get("row_number")` → always `None`. That `None` flows into `mark_as_posted(EXCEL_PATH, quote_data["row_number"], post_id)`, whose loop never matches any row and — because `src/core/excel_reader.py`'s `mark_as_posted` prints its success message **unconditionally**, outside the loop's match check — logs a false "Marked row None as posted" while the Excel dedup ledger is silently never updated for any studio-authored post. It also means the model must invent quote text/attribution itself rather than reference the vetted `quotes.xlsx` pool, defeating the design goal of "no fabricated attributions." None of the existing studio tests catch this — every test that touches `quote` hand-constructs the old `{"row_number":..., "text":...}` shape directly in Python, bypassing the actual schema round-trip.

### Robustness spec was written but never applied

`docs/superpowers/specs/2026-06-23-pipeline-robustness-design.md` was written after a described real production incident ("raw Anthropic SDK exceptions propagate and cause the GitHub Actions job to exit 1, missing the scheduled post slot") and prescribes four fixes. **None are implemented**:
1. Broaden `studio/run.py`'s `except StudioError` to `except Exception` — still only catches `StudioError`; a raw `anthropic.APIError`/timeout/network error propagates uncaught out of `run_studio`.
2. Wrap `pipeline.py`'s `_studio_stage()` call in its own try/except — no such wrapper exists; also, `_apply_studio_decision`'s `concepts_by_id[decision.top_pick]` has no `.get()`/guard, so a hallucinated `top_pick` id raises an uncaught `KeyError` outside any studio-specific handling.
3. A `--health-check` CLI flag for cheap PR validation without paid API calls — absent from `pipeline.py`'s argparse. `daily_post.yml` still runs full `--dry-run` on every PR, which still calls Anthropic and Fal.ai (dry-run only skips the final Instagram-publish step, not steps 1-12).
4. `notify_raw` on `Notifier` and durable `logs/fallbacks.jsonl` logging — neither exists.

**The exact failure mode the spec was written to prevent — an unhandled SDK exception during a scheduled run causing a missed post slot — is still fully possible today.**

### Other confirmed issues
- `--studio` without `--manual` falls through to the real Graph API posting branch with zero human review, contradicting the design spec's explicit "human-in-the-loop, no auto-publish" scope. No code-level guard prevents this; only the current workflow configuration (which always pairs the two flags) makes it moot today.
- `pipeline.py` computes `flux_override` from the studio result once, then 20+ lines later unconditionally resets it to `""` and recomputes the identical value — the first computation is dead code, harmless today but a maintenance trap.
- Studio-mode always hardcodes `caption_variant = -1` and `controversy = ""` (`pipeline.py:450`) — silently disables the A/B-testing/controversy-hook machinery for every studio-authored post, an undocumented trade-off.
- `StudioClient._record_usage`'s read-modify-write of `data/studio_spend.json` has no file lock — a race under any overlapping invocation (e.g. `studio/` and `team/` sharing the same spend log) can lose an update and make the daily $2.00 ceiling unreliable.
- `studio/reconcile.py`'s `fetch_recent_media` has no pagination on `GET /{ig_id}/media` — once an account has posted more than one Graph API page since a pending proposal, that proposal can never be reconciled; there's also no expiry/give-up-and-log path despite the design spec calling for "retried daily for 7 days, logged if still unmatched."

---

## D. The Pipeline (main flow)

`pipeline.py:run_pipeline(dry_run, reel, manual, studio)`: init config/DB/token → slot guard (3 daily windows via `_current_slot()`, skips if already posted) → content stage (studio with legacy fallback) → comment-bait injection → FLUX prompt (studio-provided or `PromptArchitect`) → Fal.ai background image → optional non-blocking overlays → Pillow composition (`compose_post`) → optional non-blocking wallpaper series → **persist to SQLite before publish** → optional reel assembly (3 more Fal.ai calls, pattern-interrupt hook scene, dual-fallback OpenAI TTS voiceover, beat-synced ffmpeg mux) → publish branch (`--manual` → Telegram only, no Graph API call; normal → real Graph API post; `--dry-run` → skip posting) → studio proposal persisted for later reconciliation → JSONL log.

**Confirmed fixed**: the previously-known `dry_run = args.dry_run or True` bug (always-truthy) lived in `team/orchestrator.py`, not `pipeline.py` — confirmed via `git show 5d90a04 --stat` (only `team/orchestrator.py` changed). `pipeline.py`'s own `--dry-run` wiring was never broken this way and works correctly today: it skips only the Instagram-publish branch, and is threaded into `save_post(..., dry_run=dry_run)`.

**Confirmed still broken**: `--carousel` is a dead CLI flag — `parser.add_argument("--carousel", ...)` exists, but it is never read anywhere in `run_pipeline` or `__main__`; the flag's own help text admits this ("currently treated as standard post"). The Wed/Thu 09:30 UTC cron in `daily_post.yml` invokes `--carousel` expecting a carousel post but actually gets a plain single image.

---

## E. Infrastructure

**GitHub Actions** — 4 workflows, all `ubuntu-latest` + Python 3.11:

| Workflow | Trigger | Does | Notes |
|---|---|---|---|
| `daily_post.yml` | 08:00/12:00/18:00 UTC daily + Wed/Thu 09:30 UTC + `workflow_dispatch`/`pull_request` | `pipeline.py --studio --manual` (or `--carousel`); commits `data/pipeline.db` + `logs/` back to repo | Validates 7 required secrets up front; `git add -f` bypasses `.gitignore`; `git push \|\| echo "⚠️ push failed"` swallows push failures silently; **PR runs still call paid Anthropic/Fal.ai APIs** despite being a "dry run" |
| `analytics.yml` | 08:00 UTC daily + `workflow_dispatch`/`pull_request` | `studio.reconcile` (non-blocking `\|\| echo`) + `src.analytics.metrics` (Meta Insights ingestion); commits DB back | **Also fires at 08:00 UTC — races `daily_post.yml` for the same `git push` on `data/pipeline.db`**; its own DB-push step has *no* failure tolerance (inconsistent with `daily_post.yml`'s pattern for the identical operation) |
| `refresh_music.yml` | Mon 06:00 UTC + `workflow_dispatch` | Pixabay music refresh, cached by ISO week | Gracefully no-ops if `PIXABAY_API_KEY` unset |
| `trending_music.yml` | Mon 10:00 UTC | Sends a manual Telegram/Slack reminder to refresh trending sounds by hand | Overlaps in purpose/day with `refresh_music.yml`; uses raw `curl` instead of the shared `notifier` module |

**No workflow runs `pytest` or `ruff`** despite both being declared dev dependencies — there is no CI test gate at all; a regression is only caught in production. **No workflow has an `if: failure()` alerting step** — a broken scheduled run (secret validation, pipeline error, ffmpeg error, push error) produces no Telegram/Slack notification, only GitHub's own UI/email.

**State**: SQLite (`data/pipeline.db`), committed to git as the sole persistence mechanism (no managed DB service). Tables are created ad hoc across multiple files (`data_store.init_db()` plus lazy `CREATE TABLE IF NOT EXISTS` scattered in `hook_tracker.py`, `competitor.py`, `predictive_scoring.py`) — no migration framework, and (see §J) at least one migration function is never invoked, leaving a documented feature permanently inert.

**API integrations**: Anthropic (studio/team reasoning + quote regen + prompt enhancement — `src/prompts/architect.py` still hardcodes the outdated `claude-3-haiku-20240307` model string while everything else in `studio/settings.py` uses `claude-haiku-4-5`), Fal.ai FLUX (backgrounds), Cloudinary (image hosting for Graph API upload), Meta Graph API v22.0 (posting — has genuinely good retry/backoff and token-sanitizing error handling), OpenAI TTS (voiceover), Pixabay (music), Telegram Bot API + Slack webhook (notifications).

**Token refresh**: `config.py` requires `META_ACCESS_TOKEN`/`IG_ACCOUNT_ID`/Cloudinary creds but treats `META_APP_ID`/`META_APP_SECRET` as optional with no cross-field validation — yet `token_manager.py`'s refresh path uses both unconditionally whenever the stored token nears expiry, so an unset pair either silently fails the refresh call or crashes, depending on downstream handling. `refresh_token.py` is a separate, human-run, `input()`-prompted script not wired into any workflow — token rotation depends entirely on a human remembering to run it.

---

## F. Code Quality

**Strengths**: `instagram_poster.py`'s retry/backoff with token-sanitized error logging; `image_generator.py`'s 4xx-vs-transient retry distinction; consistent dataclass/schema conventions shared across `studio/` and `team/`; deliberate non-blocking `try/except` around genuinely optional enhancements (overlays, wallpapers, voiceover) so a cosmetic failure never kills a post; SQL is parameterized throughout `data_store.py` (no injection risk found); no `shell=True`, no `eval`/`exec` anywhere in the repo; secrets are never hardcoded (verified by full-repo scan) and `.env` has never touched git history (verified via `git log --all -- .env`).

**Duplication**:
- `src/analytics/save_rate.py` duplicates ~80 lines near-verbatim from `src/analytics/metrics.py` (identical SQL and formatting), with `__init__.py` re-exporting the `save_rate.py` copy — the `metrics.py` version is dead weight.
- `src/audio/download_music.py` and `trending_audio.py` are two independent Pixabay-backed downloaders that both define `download_music_for_mood()` with **incompatible signatures** — a name collision risk. `reel_composer.py` imports from `trending_audio.py`, so `download_music.py`'s more careful implementation (it validates MP3 magic bytes; `trending_audio.py` does not) is effectively unused at runtime.
- `src/audio/voiceover.py` vs `voiceover_engine.py` — two parallel TTS pipelines with contradictory hardcoded mood→voice maps (`voiceover.py` maps almost everything to `"echo"`; `voiceover_engine.py` maps `dark_philosophical`→`onyx`, etc.). `pipeline.py` tries `voiceover_engine` first and silently falls back to `voiceover` on exception, so the actual narrator voice a listener hears is nondeterministic depending on which path succeeds.
- Font-loading logic (candidate-path search + fallback) is reimplemented near-identically three times: `src/visual/brand_design.py`, `src/visual/image_composer.py`, `src/hooks/pattern_interrupt.py`.
- `team/`'s 5 "spec agent" files (`content_writer.py`, `visual_designer.py`, `audio_engineer.py`, `video_editor.py`, `engagement_strategist.py`) are structurally identical boilerplate, differing only in schema/spec type — a deliberate testability trade-off per their docstrings, but real drift surface for future prompt/schema changes.
- `src/visual/carousel_composer.py` imports five underscore-prefixed "private" helpers directly from `image_composer.py`'s internals — any refactor of `image_composer.py` can silently break the carousel composer.

**Missing error handling**:
- `src/content/generate_quotes_excel.py` and `src/core/excel_reader.py`'s `wb.save(...)` calls have no try/except — a locked/open Excel file (e.g. the user has `quotes.xlsx` open) crashes the whole run with an unhandled `PermissionError`.
- `src/audio/trending_audio.py`'s download path never validates the downloaded bytes are actually audio (unlike `download_music.py`, which checks magic bytes) — a 404/captive-portal HTML response would silently be saved and later handed to ffmpeg.
- `src/video/reel_composer.py` silently drops audio on an audio-mix failure (prints a warning, returns success anyway) — a reel can ship silent with no visible signal in the pipeline's return value or notifications.
- No agent-level error handling anywhere in `team/` — every `.run()` and `_build_feedback()` accesses response dicts with bare bracket indexing rather than `.get()` with defaults, so a malformed/missing-key LLM response raises a raw `KeyError`/`TypeError` deep inside a dataclass constructor rather than a domain-specific, catchable error.
- None of `team/`'s per-post spec schemas constrain array length (`minItems`/`maxItems`) or cross-validate `post_number` alignment between plan and specs — a short/misaligned model response silently produces a gap in the final output with no error raised anywhere in the chain.

**Confirmed live bug — `src/visual/motion_effects.py`**: inside `Easing.apply()`, `elif self == EASE_OUT_EXPO:` references the bare enum member name instead of `Easing.EASE_OUT_EXPO` — `EASE_OUT_EXPO` is not defined at module scope, so calling `.apply()` on any `Easing` member besides `LINEAR`/`EASE_IN_OUT_QUAD` raises `NameError`. This is dormant only because `.apply()` is never actually called anywhere in `src/` today — but it means the module's entire six-curve "physics-informed easing" feature is unusable the moment anything calls it. Compounding this: the ffmpeg zoompan-expression builders that *are* used in production (`_build_zoom_expression`, `_build_pan_expressions`, `_build_tilt_expression`) accept an `easing` parameter but never reference it, always computing a straight linear interpolation — so even setting aside the `NameError`, no Ken Burns move in any Reel is actually eased today, despite the module's docstring claiming "natural camera feel."

**Other confirmed bugs**:
- `src/video/reel_composer.py` computes a beat-synced `transition_type` from `beat_sync.py`'s analysis, then two lines later unconditionally overwrites it with `MotionEngine.random_transition(seed=hash(timestamp) % 10000)` — the beat-sync work is logged but discarded; every transition is actually a random pick.
- `src/analytics/competitor.py`'s `DB_PATH` resolves one directory level too shallow (`src/data/pipeline.db` instead of the repo-root `data/pipeline.db` every other module uses) — competitor snapshots are written to an isolated, effectively orphaned SQLite file that no report code ever reads back from.
- `src/content/script_01_assembler.py` is dead/orphaned code from a different project: it hardcodes `~/viral-lab/output/...` paths that don't exist in this repo, and contains a literal broken filename `"src.audio.voiceover.mp3"` (almost certainly the result of an automated import-path rewrite mangling a string literal). Should be deleted rather than left as a live, importable, misleading module.
- **The `hook_id` tracking feature is silently inert.** `src/analytics/hook_tracker.py:get_hook_performance()` explicitly checks whether `posts.hook_id` exists at query time and gracefully returns a zeroed dict if not (a documented, deliberate degrade — not a crash). The column *is* defined in a migration inside `src/video/predictive_scoring.py` (`ALTER TABLE posts ADD COLUMN hook_id TEXT` among others) — but that migration function is never called from `pipeline.py`, `data_store.py`, `team/`, or `studio/` (confirmed via repo-wide grep: zero callers outside its own file/tests). Net effect: hook-performance tracking has been silently non-functional since it shipped, with no error or log line indicating why.

---

## G. Test Coverage

**243 tests collected, 241 passed, 2 failed** (live `pytest tests/ -q` run against the local Python 3.11.11 environment — no environment workaround needed, contrary to the memory that local Python is 3.9). The 2 failures are both in `tests/test_reel_composer.py` (`test_generate_reel_success`, `test_generate_reel_silent_fallback`) and are a real `ffmpeg`/`libx264` subprocess error on this machine (`Could not open encoder before EOF`), not a Python-level assertion bug — these tests shell out to the real `ffmpeg` binary rather than mocking it, making them environment-fragile. Since no CI workflow runs `pytest` at all (§E), nobody currently knows whether these pass in the GitHub Actions Ubuntu runner either.

**A real test-integrity gap**: `tests/test_phase1_integration.py` and `tests/test_phase2_integration.py` contain test functions that `return True`/`return False` instead of asserting — pytest only fails on a raised exception, so these can silently report **PASS** even when their internal check logic evaluates to `False` (confirmed live: 8 `PytestReturnNotNoneWarning`s emitted in the actual run). Several of these are also shallow by design — e.g. one checks only `"notification_text" in sig.parameters` via `inspect.signature`, another greps the *source text* of a function for constant names rather than testing actual output, and the visual/carousel/save-bait tests check only "file exists and is > N bytes," with no content-correctness assertion.

**Genuinely strong, assertion-based test files**: `test_team_debate.py` (real round-progression/feedback-propagation/threshold-override assertions via hand-rolled fake planner/reviewer), `test_team_orchestrator.py` (exact agent call-order assertions, `ast`-based static check that `orchestrator.py` never imports `pipeline`), `test_team_dashboard.py` (full event-sequence integration test including the failure path), `test_team_models.py` (round-trip `from_dict(to_dict(x)) == x` for every dataclass, schema-shape assertions), `test_studio_client.py`, `test_studio_analyst.py` (real cache-TTL/staleness logic with actual `datetime` math), `test_studio_director.py` (verifies the exact director→copywriter→director revision call sequence), `test_studio_reconcile.py` (end-to-end through a real tmp SQLite DB), `test_data_store*.py`, `test_excel_reader*.py`, `test_token_manager.py`, `test_ab_test.py`, `tests/backend/test_receipts.py` (a well-isolated FastAPI suite, though for the unrelated `backend/` subsystem).

**Shallow/tautological**: every per-agent `team/` test file (`test_team_planner.py`, `test_team_content_writer.py`, etc.) follows an identical pattern — a fake client echoes a canned payload, and the test asserts the shape matches, which by construction can't say anything about real LLM output quality. `test_studio_strategist.py`, `test_studio_copywriter.py`, `test_pipeline_studio.py`, `test_studio_types.py` all hand-construct dataclasses directly in Python rather than round-tripping through the real JSON schema — which is exactly why the §C quote-schema/prompt mismatch is invisible to the suite; no test anywhere validates a payload against its own `*_SCHEMA` via `jsonschema.validate`. `test_imports.py` is import-only, zero behavioral assertions.

**Zero coverage** (confirmed by cross-referencing the full file list against every `tests/test_*.py`): `src/analytics/{cohort_analysis,competitor,hook_tracker,save_rate,sentiment,weekly_brief}.py`, `src/audio/{download_music,trending_audio,trending_music,voiceover,voiceover_engine}.py`, `src/video/{beat_sync,predictive_scoring}.py`, `src/visual/{brand_design,carousel_composer,export_formats,motion_effects}.py`, `src/core/{instagram_poster,notifier}.py`, `src/content/{content_formats,generate_quotes_excel,script_01_assembler}.py`, `src/engagement/`, `src/hooks/`, `src/prompts/`, `src/overlays/`, `src/wallpapers/` (entire subpackages), `generate_audio.py`, `refresh_token.py`, `studio/settings.py`, `team/live.py`, `team/prompt_loader.py`. (`tests/test_phase1..4_integration.py` do give shallow smoke coverage to some of these, but with the return-value-instead-of-assert weakness noted above.)

**No pytest config anywhere** — no `pytest.ini`/`pyproject.toml`/`conftest.py`; every test file re-does its own `sys.path.insert`. The untracked, on-disk-only `socrates_pipeline/` legacy tree also has its own `tests/` with filenames that collide with root `tests/`, so a bare `pytest` from repo root needs an explicit `--ignore=socrates_pipeline` (confirmed present as a stale, no-longer-matching entry in `.pytest_cache/v/cache/lastfailed`).

---

## H. Security

- `.env` correctly `.gitignore`d and **confirmed never committed** to git history on any branch/ref (`git log --all -- .env`, `git log -p --all -- .env`, `git log --all --source --remotes -- .env` all empty).
- Full-repo scan for hardcoded API keys/tokens/passwords (`sk-...`, `AIza...`, `api_key=`, `Bearer ...`, etc.) — **zero hits** in tracked or untracked source. All secrets load via `config.py`'s `os.environ`/`python-dotenv` path.
- No `shell=True`, no `eval`/`exec` anywhere. SQL is parameterized throughout `data_store.py`. One f-string SQL construction exists in `predictive_scoring.py`'s (unused/orphaned — see §F) migration function, but its inputs are fixed literals, not user data — a latent code-smell, not an active injection vector.
- **`backend/`'s receipt-upload endpoint has no authentication** and uses the privileged Supabase *service* key — any caller can POST arbitrary files under any syntactically-valid `user_id` (regex-allowlisted, path-traversal-guarded, but otherwise open). Orphaned from the content pipeline but shares the same `.env`/secrets surface and is deployed publicly via Vercel — a real exposure if that deployment is reachable.
- **`.gitignore` coverage is undermined by already-tracked files and CI force-adds.** `logs/posts.jsonl` is tracked despite `logs/` being ignored (because `daily_post.yml` does `git add -f data/pipeline.db logs/`, bypassing the ignore rule on every scheduled run) — post history is being committed to public git history going forward, not a secrets leak but an unintended-persistence/bloat issue. 18 `output/*.jpg` files (~3.1MB) and 7 `audio/*.mp3` files (~436KB) are tracked despite matching `.gitignore` patterns — leftovers from before the ignore rules were added; the rules can't retroactively untrack them. `.DS_Store` (×3) and a stray `server.log` are also tracked.
- Token refresh being effectively unreliable (§E) means the long-lived Meta access token in the GitHub secret doesn't reliably auto-rotate — a reliability/security risk if that token has a real expiry window and no one is manually running `refresh_token.py`.
- Repo-wide `git status`/`git count-objects` shows no other hygiene red flags — `.git` is 26MB with 711 loose objects (0 packs) and 5 leftover garbage/tmp objects from an interrupted operation; a `git gc` would be a reasonable, low-priority cleanup.

---

## I. Performance / Cost

- Reel generation runs 3 full sequential Fal.ai image-generation calls per post with no shared retry/backoff (unlike the Graph API client's careful handling) — a single Fal.ai hiccup on any of the 3 can abort an entire reel.
- The team pipeline chains up to 8 sequential LLM calls per run (worse with debate rounds), with **no `over_daily_ceiling()` check anywhere in `run_team_pipeline`**, unlike `studio/run.py` which checks it up front — the one spend-governance mechanism the codebase has is bypassed entirely for the most expensive path in the repo (Opus-tier content writer, up to 3× debate rounds).
- `StudioClient._record_usage`'s spend-log read-modify-write has no file lock — under any overlapping invocation (team + studio sharing `data/studio_spend.json`), spend numbers — and thus the $2.00/day ceiling gate — can silently under-report.
- `_PRICING` in `client.py` silently defaults to Opus-tier pricing for any unrecognized model string — a typo'd model ID in `ROLE_MODELS` would silently mis-price spend rather than error.
- Non-blocking best-effort design (overlays, wallpapers, voiceover, notifications all wrapped in broad `except Exception`) is good for pipeline resilience but makes partial failures easy to miss without close log reading — several of the confirmed bugs above (silent audio drop, silently-broken hook tracking, false-success Excel logging) are exactly this pattern: a failure that never surfaces anywhere.
- Two GitHub Actions workflows (`daily_post.yml`, `analytics.yml`) both fire at `08:00 UTC` and both commit+push the same binary SQLite file — a genuine race where one run's `git push` can silently clobber the other's DB state (SQLite files don't merge).

---

## J. What Is Broken (ranked, most consequential first)

1. **Studio quote schema vs. strategist prompt contradiction** (§C) — breaks pool-anchored quote selection and Excel dedup tracking for every studio-authored post; false "success" is logged while nothing is actually written.
2. **Studio failures aren't fully fail-safe** (§C) — a raw SDK exception or a hallucinated `top_pick` id can crash an entire scheduled run instead of falling back to legacy, exactly reproducing the incident the (unapplied) robustness spec was written to fix.
3. **`src/visual/motion_effects.py`'s `NameError`** on `EASE_OUT_EXPO`, compounded by the fact that easing is never actually applied to any Ken Burns move even where it would work — the entire "physics-informed camera motion" feature is non-functional.
4. `reel_composer.py` computes a beat-synced transition type, then discards it in favor of a random pick — beat sync doesn't actually affect transitions despite being logged as if it does.
5. `hook_tracker.py`'s performance tracking is silently inert — the migration that adds the column it reads (`posts.hook_id`) is defined but never invoked anywhere.
6. `--carousel` is a dead CLI flag; the Wed/Thu scheduled "carousel" posts are actually plain single images.
7. `team/orchestrator.py`'s unapproved-plan bug (§B) — a plan the reviewer explicitly rejected after 3 rounds is unconditionally labeled and saved as "approved," and 5 more paid LLM calls build on it anyway.
8. `team/orchestrator.py`'s `dry_run` parameter does nothing at all — fully dead, by design, pending unbuilt future work.
9. Token auto-refresh is unreliable — `META_APP_ID`/`META_APP_SECRET` are optional in `config.py` with no cross-field validation against `token_manager.py`'s unconditional use of both.
10. `src/audio/trending_audio.py`'s `FALLBACK_TRACKS` dict contains several fabricated-looking hex filenames (e.g. `audio_1a2b3c4d5e.mp3`) that will 404 — that mood's music fallback path is fully broken for at least `epic_warrior` and `stark_minimal`.
11. `src/content/script_01_assembler.py` is dead/orphaned code from a different project (`~/viral-lab/...` paths, a mangled literal filename) — should be deleted, not left importable.
12. `src/analytics/competitor.py`'s `DB_PATH` resolves to the wrong directory — competitor snapshots are written to and read from an orphaned, effectively-empty SQLite file.
13. Test-suite integrity: `test_phase1_integration.py`/`test_phase2_integration.py` can silently pass on broken logic (return-value instead of assert pattern).
14. `socrates_pipeline/` — a legacy, untracked, on-disk duplicate of much of `src/` with its own colliding test filenames — sits alongside the real tree, a confusion/maintenance risk for anyone who edits the wrong copy (two prior commit messages, `f2cf355` and `dc9128b`, corroborate an incomplete migration off of it).

---

## K. What Is Missing (documented but not built, or built but unwired)

The docs-to-code gap is smaller than the aspirational-sounding doc titles suggest — most planned features (beat sync, trending music, voiceover, the team dashboard, the AI studio, SQLite state, A/B testing, cohort analysis, predictive scoring, TikTok/YouTube export) are genuinely implemented, in some cases exceeding their original spec. Real gaps:

- **`--health-check` CLI mode** (`pipeline-robustness-design.md`) — not present; PR-time "dry runs" still call paid Anthropic/Fal.ai APIs.
- **The entire `team/` system is fully built, tested, and unused in production** — a complete, parallel 8-agent pipeline with no integration point into `pipeline.py`. Its own plan doc's central integration goal ("pipeline.py is modified to optionally accept a team_output parameter") was never implemented.
- **X/Twitter thread automation, LinkedIn/Pinterest/Substack cross-posting, Amazon affiliate links** — all described with specific implementation hooks in `docs/VIRAL_STRATEGY_2026.md` (e.g. a proposed `AMAZON_ASSOCIATE_TAG` env var) but zero corresponding code or `.env.example` entries exist.
- **Fake iOS notification banner hook, 3D text, QR badges, HDR grading, 60fps export, "Golden 15" (`:13`/`:47`) posting-time offsets** — named as concrete implementation items in `QUALITY_UPGRADE_ROADMAP_100.md`/`VIRAL_OPTIMIZATION_BRIEF.md`; none found. Cron schedules remain on round `:00`/`:30` marks.
- `src/analytics/competitor.py` is manual-entry only (no scraping/automation) — reasonable by design, but not obviously flagged as such to a casual reader of the module name.
- `src/analytics/sentiment.py` is fully implemented but **unwired** — nothing in the pipeline fetches IG comments to feed it.
- `studio/reconcile.py`'s documented "retried daily for 7 days, then logged as unmatched" reliability behavior doesn't exist — it has no expiry or give-up/log path, and no pagination, so it can permanently fail to reconcile once enough new posts accumulate.
- No top-level `README.md` — for a project with this much operational surface (4 workflows, 10+ required secrets, three overlapping AI-agent systems, a bolted-on second product), the absence of a setup/onboarding doc is a real gap; `.env.example` and the various `docs/*.md` files only partially substitute.

---

## L. Top 10 Recommendations, Ranked by Impact

1. **Fix the studio quote schema/prompt contradiction** (`studio/types.py` `CREATIVE_BRIEF_SCHEMA["quote"]` vs `studio/strategist.py`'s prompt) — this silently breaks quote-pool selection and Excel dedup for every studio-authored post today; either loosen the schema to allow `row_number`/`need_new` or rewrite the prompt to match the current strict `text`/`author` shape, and add a test that validates real payloads against the actual schema.
2. **Apply the already-written robustness spec**: broaden `studio/run.py`'s exception handling beyond `StudioError`, wrap `pipeline.py`'s `_studio_stage()` call in try/except, guard `concepts_by_id[decision.top_pick]`. This directly prevents a repeat of the production incident the spec describes — a missed scheduled post from an unhandled SDK exception.
3. **Fix `src/visual/motion_effects.py`'s `EASE_OUT_EXPO` `NameError`** and actually apply the `easing` parameter inside `_build_zoom_expression`/`_build_pan_expressions`/`_build_tilt_expression` — one-line crash fix plus making a fully-built, well-documented feature (physics-informed camera motion) actually do something.
4. **Decide the team system's fate.** It's fully built, extensively tested, and completely unused in production. Either wire it into the scheduled pipeline (per its own plan doc's original integration goal) or explicitly document it as an experimental/manual-only tool, so future work doesn't keep building two parallel agent systems. While deciding, fix the unapproved-plan-reported-as-approved bug (§B/§J.7) — it's the single most consequential live logic bug in that subsystem.
5. **Add a CI test gate.** No workflow runs `pytest` today; add one on every PR (mocking or skipping the 2 ffmpeg-dependent tests as needed) so regressions are caught before a scheduled run fails in production instead of after.
6. **Fix or remove `--carousel`.** Either wire `args.carousel` into `run_pipeline` to build a real carousel post, or drop the flag and stop scheduling `--carousel` runs — right now the Wed/Thu schedule silently doesn't do what its name implies.
7. **Fix the CI DB-push race**: `daily_post.yml` and `analytics.yml` both trigger at 08:00 UTC and both `git push` the same SQLite file — stagger the schedules or move to a lock/merge-safe persistence approach before a lost-write silently corrupts A/B/analytics state.
8. **Wire (or delete) the orphaned `predictive_scoring.py` migration** that `hook_tracker.py` depends on — currently a fully-built analytics feature has been silently inert since it shipped with no error to indicate why.
9. **Secure or remove the `backend/` receipt API.** Unauthenticated, uses a privileged Supabase service key, and is orphaned from the content pipeline — add auth before it's ever exposed, or move it out of this repo/Vercel project.
10. **Consolidate the duplicated modules**: merge `save_rate.py` into `metrics.py`, pick one of `trending_audio.py`/`download_music.py` as the real music-fetch path (delete the other's fabricated fallback URLs from whichever is discarded), unify the two voiceover mood-maps, and delete the orphaned `src/content/script_01_assembler.py`.
