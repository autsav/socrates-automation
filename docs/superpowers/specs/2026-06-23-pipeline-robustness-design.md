# Pipeline Robustness + Health-Check Design

**Date:** 2026-06-23
**Scope:** Make `pipeline.py` resilient to AI Creative Studio failures, add a cheap health-check mode for PRs, and keep scheduled Instagram posts flowing.

---

## 1. Problem Statement

After merging the Creative Studio branches into `main`, scheduled posts run with:

```bash
python pipeline.py --studio --manual
```

The workflow claims "auto-falls back to legacy templates if the studio fails", but the current implementation only catches `StudioError`. Raw Anthropic SDK exceptions (`anthropic.NotFoundError`, `APIError`, network errors) propagate and cause the GitHub Actions job to exit 1, missing the scheduled post slot.

Additionally, the PR safety check currently runs `--dry-run`, which calls real APIs and can fail for key/network reasons unrelated to code correctness.

---

## 2. Goals

1. **Guaranteed fallback:** Any failure inside the studio stage must switch to the proven legacy templated path, not crash.
2. **Human visibility:** When fallback happens, alert via Telegram/Slack if configured; otherwise log loudly.
3. **Cheap PR validation:** Add `--health-check` that verifies imports, config parsing, DB init, quote pool, and directory write without calling paid APIs.
4. **No missed slots:** The scheduled workflow should exit 0 when a post is generated and delivered to Telegram, even if studio failed.

---

## 3. Design

### 3.1 Exception Handling in the Studio Chain

**File:** `studio/run.py`

Current `run_studio()`:

```python
try:
    perf = analyst.get_or_build_brief(client)
    brief = strategist.make_brief(client, perf, slot, recent_posts, pool)
    concepts = copywriter.draft(client, perf, brief)
    decision = director.review(client, perf, brief, concepts)
    cmap = {c.id: c for c in concepts}
    return brief, decision, cmap
except StudioError as e:
    log.warning("[studio] agent failure (%s) — falling back to legacy", e)
    return None
```

Change to:

```python
try:
    perf = analyst.get_or_build_brief(client)
    brief = strategist.make_brief(client, perf, slot, recent_posts, pool)
    concepts = copywriter.draft(client, perf, brief)
    decision = director.review(client, perf, brief, concepts)
    cmap = {c.id: c for c in concepts}
    return brief, decision, cmap
except Exception as e:
    log.warning("[studio] agent failure (%s) — falling back to legacy", e, exc_info=True)
    return None
```

Also broaden `_build_pool()` to return an empty list on any read/parsing error rather than crashing.

**File:** `pipeline.py`

Wrap `_studio_stage()` call in `run_pipeline` in its own try/except so even unexpected errors inside the studio stage are caught:

```python
if studio:
    log.info("Step 1: AI Creative Studio...")
    try:
        bundle = _studio_stage(cfg, slot)
    except Exception as e:
        log.warning("[studio] stage crashed (%s) — falling back to legacy", e, exc_info=True)
        bundle = None

    if bundle is not None:
        quote_data, studio_decision = bundle
        ...
    else:
        log.info("[studio] fell back to legacy templated path")

if studio_decision is None:
    log.info("Step 1: Reading quote + legacy templated content...")
    quote_data, mood, controversy, caption_variant = _legacy_content(cfg)
```

### 3.2 Fallback Alert

Add `_notify_studio_fallback(...)` in `pipeline.py`:

```python
def _notify_studio_fallback(cfg, slot, reason):
    message = f"⚠️ Studio failed for slot {slot}: {reason}. Used legacy fallback."
    log.warning(message)
    try:
        notifier = Notifier(cfg)
        notifier.notify_raw(message)
    except Exception:
        _write_fallback_log(slot, reason)
```

If `Notifier.notify_raw` does not exist, extend `notifier.py` to add a simple plain-text notification method that sends to Telegram (preferred) or Slack.

Also write a durable log entry to `logs/fallbacks.jsonl`:

```python
{
  "timestamp": "20260623_120000",
  "slot": "12:00",
  "reason": "anthropic.NotFoundError: model 'claude-sonnet-4-6' not found",
  "fallback": true
}
```

### 3.3 Health-Check Mode

Add `--health-check` argument to `pipeline.py`. In this mode the script:

1. Imports all top-level modules (`studio.*`, `image_generator`, `excel_reader`, etc.).
2. Loads `Config()`.
3. Calls `data_store.init_db()` and verifies `data/pipeline.db` is writable.
4. Reads the quote pool via `studio.run._build_pool()` or `excel_reader` equivalent.
5. Verifies at least one ready quote exists.
6. Creates `output/`, `logs/`, `audio/music/` if missing.
7. If `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are set, optionally sends a test ping; skips silently if missing.
8. Prints a JSON summary and exits 0.
9. On any failure, prints the failing step and exits 1 with a specific code (`HEALTH_CHECK_{STEP}`).

Implementation sketch:

```python
def run_health_check():
    results = {}
    try:
        cfg = Config()
        results["config"] = "ok"
    except Exception as e:
        return {"config": f"fail: {e}"}, 1

    try:
        init_db()
        results["database"] = "ok"
    except Exception as e:
        return {"database": f"fail: {e}"}, 1

    try:
        pool = _build_pool(str(EXCEL_PATH))
        if not pool:
            return {"quote_pool": "fail: no ready quotes"}, 1
        results["quote_pool"] = f"ok ({len(pool)} ready)"
    except Exception as e:
        return {"quote_pool": f"fail: {e}"}, 1

    try:
        for d in (OUTPUT_DIR, LOG_DIR, PROJECT_ROOT / "audio" / "music"):
            d.mkdir(parents=True, exist_ok=True)
        results["directories"] = "ok"
    except Exception as e:
        return {"directories": f"fail: {e}"}, 1

    return results, 0
```

### 3.4 Workflow Updates

**File:** `.github/workflows/daily_post.yml`

Replace PR step:

```yaml
      - name: Run pipeline (dry-run on PRs)
        ...
        run: |
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            echo "🔍 PR health-check"
            python pipeline.py --health-check
          ...
```

Keep scheduled and manual dispatch runs on `--studio --manual`.

Add a step after the pipeline run to surface fallback counts:

```yaml
      - name: Report studio fallback
        if: always()
        run: |
          if [ -f "logs/fallbacks.jsonl" ] && [ -s "logs/fallbacks.jsonl" ]; then
            echo "⚠️ Studio fallback occurred:"
            tail -n 1 logs/fallbacks.jsonl
          fi
```

**Node 20 deprecation warning:** `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/upload-artifact@v4` are already the latest stable major versions. The warning comes from GitHub forcing Node 20 actions onto Node 24 runners. No repository change is required; monitor for new major versions and upgrade when released.

---

## 4. Files to Change

- `studio/run.py` — broaden exception handling in `run_studio` and `_build_pool`
- `pipeline.py` — wrap `_studio_stage`, add `--health-check`, add fallback alert/logging
- `notifier.py` — add `notify_raw` plain-text helper (if missing)
- `.github/workflows/daily_post.yml` — use `--health-check` on PRs, add fallback report step

---

## 5. Success Criteria

1. `python pipeline.py --dry-run --studio` with a broken Anthropic key/model returns to the legacy path and completes without crashing.
2. `python pipeline.py --health-check` exits 0 on a properly configured repo with ready quotes.
3. PR workflow passes using `--health-check` without calling Anthropic/Fal/Meta APIs.
4. Scheduled workflow with a studio failure still produces an image and sends it to Telegram.
5. A fallback entry appears in `logs/fallbacks.jsonl` and (if configured) a Telegram/Slack alert is sent.

---

## 6. Out of Scope

- Changing the Creative Studio agent logic itself.
- Adding new agents or content features.
- Refactoring unrelated parts of `pipeline.py` beyond the fallback/health-check wiring.
- Replacing GitHub Actions action versions for the Node 20 deprecation unless a newer major release is available.
