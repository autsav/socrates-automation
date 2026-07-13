# Trend Scout — trending-topic hook sourcing (Sub-project NEW)

Date: 2026-07-13
Status: Approved
Depends on: Sub-project B (content injection `--content` + Remotion BridgeScene)

## Goal

Grab attention by opening reels with a live trending topic (celebrity / news /
trend) that bridges to a timeless Socratic quote — "Trending hook → timeless
payoff". A studio agent fetches current trends, picks the one that bridges most
naturally and safely, and writes the hook + bridge line. Falls back to the
evergreen hook whenever no safe bridge exists. Runs headless in the CI cron.

## Creative model

`Trending Hook → Bridge → Quote → CTA`. The trend is bait; the quote is the
substance. Brand-safe: we ride the topic's attention, never make factual claims
about real people.

## Prerequisite (done)

`GNEWS_API_KEY` set in `.env` (validated live). Google Trends needs no key.

## Components

### 1. Trend sources — `src/content/trend_sources.py`
- `google_trends(limit=15) -> list[str]` — US daily trending searches via
  `pytrends`. No key. On any error/rate-limit → `[]`.
- `gnews_headlines(limit=10, api_key) -> list[str]` — `GET https://gnews.io/api/v4/top-headlines`
  (`apikey`, `lang=en`, `category=general`), returns article titles. On error → `[]`.
- `fetch_trends(cfg, limit=20) -> list[dict]` — merge + dedupe both into
  `[{topic, source}]`. Per-source failure is skipped; both empty → `[]`.

### 2. Trend Scout agent — `studio/trend_scout.py`
New studio role `trend_scout` (sonnet, medium; shares the daily spend ceiling).
- `pick_hook(client, candidates, quote_ctx) -> TrendHook` — one LLM call. Input:
  the candidate trends + the reel's chosen quote/theme/audience. Output `TrendHook`:
  `{used: bool, topic, source, hook, bridge, rationale}`.
  - Selects the single trend that bridges most naturally to the quote's theme.
  - `hook`: 5–12 words, formula-compliant (negative framing where apt), references
    the trend as bait.
  - `bridge`: the "…but 2,400 years ago Socrates already knew…" pivot connecting
    trend → quote (uses But/Therefore momentum).
  - `used: false` when NO candidate bridges cleanly and safely.
- **Safety guardrails (prompt, hard rules):** never assert a real person said/did
  a specific thing; reject tragedy/death/disaster, war/hard-politics/violence,
  medical or financial advice, protected-class or defamatory angles. Prefer
  evergreen-adjacent trends (money, work, burnout, success, AI, habits,
  discipline, relationships, ambition). When unsure, set `used: false`.
- Types `TrendHook` + `TREND_HOOK_SCHEMA` in `studio/types.py`.

### 3. Integration — `pipeline.py`
- New helper `_apply_trend_scout(cfg, quote_data) -> quote_data`: when
  `GNEWS_API_KEY` + `ANTHROPIC_API_KEY` are present and not over the spend ceiling,
  `fetch_trends` → `pick_hook`; if `used`, set `quote_data["hook"] = th.hook` and
  `quote_data["bridge"] = th.bridge`. Otherwise return `quote_data` unchanged
  (evergreen). Never raises.
- Called in the reel content path after the base content is chosen (legacy or
  studio), before hook finalization. The bridge then renders via B's BridgeScene;
  the trend hook flows through B's hook validator.
- **Trigger: always-on** when the keys are present (self-gating via the `used:false`
  safety fallback). No flag.

### 4. Config / deps
- `GNEWS_API_KEY` in `config.py` + `.env.example` (key already in `.env`).
- Add `pytrends` to `requirements.txt`.
- Add `GNEWS_API_KEY` to the `daily_post.yml` pipeline step env (like
  `JAMENDO_CLIENT_ID`) so it activates in production.

## Data flow

```
base quote_data (legacy/studio) ─▶ _apply_trend_scout
     fetch_trends(cfg): pytrends[] + gnews[] ─▶ candidates
     pick_hook(client, candidates, quote_ctx) ─▶ TrendHook
        used? ─ yes ▶ quote_data.hook = trend hook ; quote_data.bridge = bridge
              └ no  ▶ unchanged (evergreen hook, no bridge)
                          │
             B: hook validator + BridgeScene render + publish
```

## Fallback chain (never crashes a reel)

missing key → both sources empty → agent error → `used:false` ⟶ evergreen hook
(today's behavior), no bridge scene. Each step logs and continues.

## Safety (why the guardrails matter)

Live headlines include hard-politics/conflict/tragedy items (verified in the GNews
sample). The agent MUST reject these and only bridge from safe, evergreen-adjacent
topics. Riding a topic for attention is fine; asserting facts about real people is
not. When in doubt → evergreen.

## Out of scope (YAGNI)

- Reactive hot-takes / claims about real people (rejected creative model).
- Trending-audio matching (the reel uses the fixed sage VO + Jamendo bed).
- Verifying headline truth (we never restate a headline as fact — we bridge the
  topic to a timeless idea).

## Testing

- `google_trends` / `gnews_headlines`: monkeypatch the HTTP/lib layer → parse
  titles; error → `[]`. `fetch_trends`: merges + dedupes; one source down → still
  returns the other; both down → `[]`.
- `pick_hook`: `_SeqClient` mock returns a `TrendHook`; assert schema-valid, and
  the `used:false` path yields no hook/bridge.
- `_apply_trend_scout`: no `GNEWS_API_KEY` → agent not called, quote_data
  unchanged; `used:true` → hook+bridge set; `used:false` → unchanged; agent
  exception → unchanged (never raises).
- Integration: with keys stubbed and a `used:true` mock, a reel renders with a
  bridge scene; without keys, evergreen 3-scene reel.
