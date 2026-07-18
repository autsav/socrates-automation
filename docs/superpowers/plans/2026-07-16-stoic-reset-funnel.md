# Stoic Reset Funnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the £12 "Stoic Reset Journal" (Claude-generated, Telegram-approved, Gumroad) and the automated trigger-comment → public-reply → bio funnel.

**Architecture:** Product = one-shot generator script (Claude JSON → branded HTML → headless-Chrome PDF → Telegram). Funnel = `posts.trigger_keyword` registry filled at post time + hourly `funnel_worker` sweep reusing `engagement_bot.fetch_comments/post_reply` with word-boundary matching, replied-log dedup, and templated bio-steering replies.

**Tech Stack:** Python 3.11 (`.venv/bin/python`), SQLite, Instagram Graph API (existing wrappers), headless Chrome for PDF, GitHub Actions hourly cron.

## Global Constraints

- Never-crash: every Graph/LLM/Chrome call best-effort; a failure skips and continues.
- Additive DB migrations only; `data/pipeline.db` stays token-free; `git checkout -- data/pipeline.db` before commits after runs.
- No new Python deps (Chrome binary for PDF, auto-detected; skip when absent).
- funnel cron must NOT commit/push the DB (no third writer in the push race).
- No CTA may promise a DM.

---

### Task 1: CTA honesty + trigger-keyword registry
**Files:** Modify `pipeline.py` (`_CTA_VARIANTS`, `_pick_cta` extraction, `save_post` callsites), `src/core/data_store.py` (migration + `record_trigger_keyword`). Test: `tests/test_funnel_registry.py`.
**Produces:** `data_store.record_trigger_keyword(row_id, kw)`; `pipeline._extract_trigger_keyword(cta) -> str|None` (regex `Comment '([A-Za-z]+)'`); posts saved with a trigger CTA carry `trigger_keyword`.
Steps: failing tests (extraction; migration; honesty guard `not re.search(r"DM('| )?(you|s)", v, re.I)` over `_CTA_VARIANTS`) → implement → green → commit.

### Task 2: funnel_worker
**Files:** Create `src/engagement/funnel_worker.py`. Test: `tests/test_funnel_worker.py`.
**Produces:** `run_funnel_sweep(cfg, lookback_posts=10, fetch=engagement_bot.fetch_comments, reply=engagement_bot.post_reply) -> {"posts_checked","comments_matched","replies_sent"}`; `_matches(keyword, text)` word-boundary case-insensitive; replied-log reuse (`auto_reply.REPLIED_LOG_PATH` format); rotating `REPLY_TEMPLATES` (no DM promises); tally appended to `data/funnel_log.json`; `__main__` CLI.
Steps: failing tests (match/word-boundary; dedup; one-bad-post isolation; tally; templates honesty) → implement → green → commit.

### Task 3: hourly cron
**Files:** Create `.github/workflows/funnel.yml`. Test: extend `tests/test_workflow_reliability.py` (yaml loads; no `git push` in funnel.yml).
Hourly cron + workflow_dispatch; pip install; `python -m src.engagement.funnel_worker || echo "sweep failed (non-blocking)"`; upload `data/funnel_log.json` artifact. Commit.

### Task 4: product generator
**Files:** Create `scripts/generate_product.py`, `scripts/product_template.html`. Test: `tests/test_product_generator.py`.
**Produces:** `CONTENT_SCHEMA` (title, intro, protocol[3], daily_pages[21]{quote,prompts[3],micro_action}, seven_day[7], closing); `render_html(content) -> str` (brand tokens: `#0e0e13` ink, gold `#d8b25c`, serif headings, A5 `@page`); `html_to_pdf(html_path, pdf_path) -> bool` (Chrome autodetect: `/Applications/Google Chrome.app/.../Google Chrome`, `chromium`, `google-chrome`; False when absent); `main()` = Claude call (sonnet, one shot, schema-validated) → JSON+HTML+PDF under `output/product/` → `Notifier.send_document`.
Steps: failing tests (schema validation rejects 20-page journal; render includes brand + all 21 days; pdf skips gracefully sans Chrome) → implement → green → commit.

### Task 5: generate the real product + ship
Run `scripts/generate_product.py` live → verify PDF (page count, brand, content quality) → send to Telegram → full suite → `git checkout -- data/pipeline.db` → commit + push. Document the 3 manual steps (Gumroad upload £12, bio link, token `instagram_manage_comments`) in the run output.
