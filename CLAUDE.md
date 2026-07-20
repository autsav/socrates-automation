# Socrates IG Pipeline — project notes for Claude

Automated daily philosophy Reels/carousels for Instagram. Entry point `pipeline.py`.
Run with the 3.11 venv: `.venv/bin/python pipeline.py …`; tests: `.venv/bin/python -m pytest`.
All scheduled slots now **auto-post directly to Instagram** via the Graph API (no more --manual in the cron).

## Reel flow (POV / `--remotion`)
Content stage (`--content` JSON → studio `--studio` → legacy excel) sets `quote_data`
→ `_apply_trend_scout` (optional trending hook+bridge) → `_run_pov_reel`:
edge-tts sage VO + Jamendo music + Remotion render → post / Telegram-manual.
Arc: **Hook → [Bridge] → Quote → CTA** (bridge scene only when `quote_data["bridge"]` set).

## Features (2026-07-13)
- **`--content <json>`** bypasses excel+studio (hook/bridge/quote/cta/caption/hashtags/mood/
  attribution/audience/row_number; missing fields fall back to generators; `row_number:null`
  skips excel marking).
- **Viral formula generators** in `pipeline.py`: `_enforce_hook_len` (≤12 words), `_loopify`
  (seamless-loop CTA), DM-trigger CTAs, `_generate_hashtags` clamped to 3–5 non-generic.
- **Music Director** (`studio/music_director.py`) → picks a **Jamendo** track by emotional fit.
- **Trend Scout** (`studio/trend_scout.py` + `src/content/trend_sources.py`) → live trend →
  agent-written trending hook+bridge, safety-gated (prompt **and** `is_unsafe` keyword denylist).
- **Remotion BridgeScene** (`remotion/src/components/BridgeScene.tsx`), optional 4th scene.

## Gotchas discovered (do NOT re-learn the hard way)
- **ffmpeg `rotate` filter has no `in` variable** — only `n`/`t`. `zoompan` DOES have `in`.
  A rotate angle expr using `in` → parse fail → `-22 Invalid argument` → every reel crashes.
  See `_eased_t_expr(var=…)` in `src/visual/motion_effects.py` (tilt uses `n`, zoom/pan use `in`).
- **Pixabay has NO public music API** (`/api/music/` 404s). Music is **Jamendo** (`JAMENDO_CLIENT_ID`).
  Jamendo `fuzzytags` must be **space-joined** (requests encodes a literal `+` to `%2B`).
  Always post-filter Jamendo hits on `audiodownload_allowed`.
- **pytrends `trending_searches` 404s** (Google deprecated it). Trend Scout runs on **GNews**;
  Google Trends is a graceful `[]` skip.
- **edge-tts uses the Python API** (`Communicate(boundary="WordBoundary")`), NOT the CLI — no PATH
  needed. Reel sage voice = `en-US-AndrewNeural`, rate `-30%`, pitch `-14Hz` (`REEL_VOICE/RATE/PITCH`).
- **`data/pipeline.db` is NOT git-tracked (security decision 2026-07-20, c23a260)** —
  gitignored; CI persists it via Actions cache (`pipeline-db-*` keys: restore at job
  start, token_state scrub, then save — in every DB-touching workflow). Never
  `git add -f` it; the guard tests enforce ignored + never-committed.
- **GitHub Actions cron needs all 12 secrets set** (`gh secret set …`); the `Validate required secrets`
  step `exit 1`s the whole job if any of the 7 required is missing. Optional: JAMENDO/GNEWS/OPENAI/TELEGRAM×2.

## Conventions
- Studio agents: module with `_PREFIX`/`_ROLE`, call `client.call(role, prefix, role_system, user, schema)`,
  parse via `SomeType.from_dict`. Roles/models in `studio/settings.py`; types+schemas in `studio/types.py`.
- Never crash a reel: every optional stage (trend/music/VO/bridge) is try/except best-effort → fallback.
- Specs/plans live in `docs/superpowers/`.
