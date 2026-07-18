# Stoic Reset Funnel — Design Spec

**Date:** 2026-07-16
**Status:** Approved design → implementation
**Goal:** Turn the pipeline's dead-end DM-trigger CTAs into a real revenue funnel: a Claude-generated paid product (£12 Gumroad PDF) + an automated comment→bio→checkout path. First monetization of the account.

---

## 1. Locked decisions (brainstorm)

| Decision | Choice |
|---|---|
| **Product** | Paid digital product now: *The Stoic Reset Journal*, £12 on Gumroad (not email-first, not affiliate). |
| **Build** | Claude generates the full journal; human approves via Telegram; one-time manual Gumroad upload. |
| **Funnel wiring** | Auto **public comment reply** + bio link (no DM API / no ManyChat). Uses existing Graph-API comment infra. |
| **CTA honesty** | Rewrite `_CTA_VARIANTS` — no "I'll DM you" promises; replies steer to bio. |

## 2. What already exists (reused)

- `src/engagement/engagement_bot.py`: `fetch_comments(media_id, token)` (GET `/{media}/comments`) and `post_reply(comment_id, text, token)` (POST `/{comment}/replies`) — working Graph-API calls.
- `src/engagement/auto_reply.py`: `REPLIED_LOG_PATH` dedup log (`data/replied_comments.json`).
- `src/core/notifier.py`: `send_document` (PDF → Telegram) + approval flow.
- `posts` table with real IG `post_id` backfilled by `studio/reconcile.py` / `approval_daemon`.
- Reels brand (gold-on-dark, serif) to style the PDF.

**Gap:** no product, no per-post trigger-keyword record, no scheduled trigger-comment watcher, CTAs promise DMs nothing sends.

## 3. Components

### 3.1 Product generator — `scripts/generate_product.py` (one-shot, manual run)
- Claude (StudioClient not required; direct Anthropic call is fine, opus) produces structured JSON: title page copy, intro ("why resets fail"), the **3-line Reset protocol**, **21 daily pages** (each: a Stoic quote + 3 reflection prompts + 1 micro-action), a **7-day reset program**, closing page.
- JSON → HTML via a template in `scripts/product_template.html`: gold-on-dark brand, serif headings, print-sized pages (A5), page-break CSS.
- HTML → PDF via headless Chrome: `chrome --headless --print-to-pdf=out.pdf file.html` (auto-detect Chrome path on macOS; no new Python deps).
- Output: `output/product/stoic_reset_journal.pdf` + the HTML + content JSON (re-render without re-paying).
- Sends the PDF to Telegram via `Notifier.send_document` for review. **No auto-publish** — Gumroad upload is a documented manual step.

### 3.2 Keyword registry — `posts.trigger_keyword`
- Additive migration in `data_store.init_db`; new `save_post(..., trigger_keyword=None)` passthrough (or `record_trigger_keyword(row_id, kw)` if signature churn is riskier).
- `pipeline.py`: when the chosen CTA contains a `Comment 'X'` trigger, extract `X` (regex `Comment '([A-Z]+)'`) and store it on the post row.

### 3.3 CTA honesty — `pipeline._CTA_VARIANTS`
- Replace DM-promising variants with bio-honest equivalents, keeping the comment-trigger mechanic:
  - `"Comment 'RESET' and I'll DM you the 3-line Stoic reset."` → `"Comment 'RESET' and I'll point you to the 3-line Stoic reset."`
  - `"Comment 'STOIC' and I'll DM you the full reflection."` → `"Comment 'STOIC' for the full reflection — it's one tap away."`
- Guard test: no variant may contain "DM you"/"DM's"/"I'll DM".

### 3.4 Funnel worker — `src/engagement/funnel_worker.py`
- `run_funnel_sweep(cfg, *, lookback_posts=10) -> dict`:
  1. Query `posts` for the most recent N rows with a real `post_id` (not `PENDING_MANUAL_%`, not dry-run) and a non-null `trigger_keyword`.
  2. For each: `fetch_comments` → keep comments whose text matches the keyword (case-insensitive **word-boundary** match, so "RESET" ≠ "presets") → drop ids already in the replied log.
  3. Reply with a rotating on-brand template (3-4 variants, e.g. "It's waiting for you — link in bio 🔗") via `post_reply`; record id in the replied log (reuse auto_reply's log format).
  4. Tally `{posts_checked, comments_matched, replies_sent}` into `data/funnel_log.json` (append, dated) — the conversion proxy metric.
- Never-crash contract: every Graph call wrapped; a failure skips that post/comment and continues; the sweep never raises.
- CLI: `python -m src.engagement.funnel_worker` (used by cron + manual runs).

### 3.5 Cron — `.github/workflows/funnel.yml`
- Hourly (`0 * * * *`), ~1-minute job: checkout, pip install, run the sweep. Secrets: `META_ACCESS_TOKEN`, `IG_ACCOUNT_ID` (+ `ANTHROPIC_API_KEY` unused in v1 — replies are templated, not LLM, to keep the job fast and free). Non-PR only; never fails the workflow (best-effort `|| echo`).
- Note: does NOT commit the DB (read-only w.r.t. pipeline.db; funnel_log.json is workflow-local, uploaded as artifact) — avoids adding a third DB-push race.

### 3.6 One-time manual steps (README section in the spec dir)
1. Create Gumroad product from `output/product/stoic_reset_journal.pdf`, price £12.
2. Set the IG bio link to the Gumroad URL.
3. Confirm the Meta token has `instagram_manage_comments` (already assumed by engagement_bot).

## 4. Testing

- **Product:** content-JSON schema validation (21 daily pages, protocol present); HTML render includes brand tokens; Chrome/PDF step auto-skipped when Chrome absent (CI).
- **Registry:** migration adds column; keyword extracted from CTA text (`Comment 'RESET' …` → `RESET`); posts without triggers store NULL.
- **CTA honesty:** no `_CTA_VARIANTS` entry matches `/DM('| )?(you|s)/i`.
- **Worker:** word-boundary matching (RESET matches "reset 🙏", not "presets"); dedup vs replied log; mocked `fetch_comments`/`post_reply`; per-post failure isolation (one bad post doesn't stop the sweep); tally correctness.
- **Cron:** yaml validity; workflow does not `git push`.

## 5. Non-goals (v1)

- No DM automation, no ManyChat, no email capture, no landing page, no UTM analytics (Gumroad's own stats suffice until there is traffic).
- No LLM-generated funnel replies (templated in v1; AutoReplyEngine stays for the burst bot).
- No auto-upload to Gumroad.

## 6. Success criteria

1. `scripts/generate_product.py` produces a branded PDF and delivers it to Telegram.
2. A post saved with a `Comment 'RESET'` CTA has `trigger_keyword='RESET'` in the DB.
3. `run_funnel_sweep` (mocked Graph) replies exactly once per matching comment and logs the tally.
4. No CTA promises a DM. Full suite green.
