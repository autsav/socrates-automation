# Social Strategist Agent — Design Spec

**Date:** 2026-07-28
**Status:** Design approved, awaiting spec review then plan
**Author:** Claude (brainstorming session)

## Goal

Add a new Socrates studio agent (`social_strategist`) that generates complete Instagram content packages (hook, bridge, quote, CTA, caption, hashtags, mood, attribution, audience) using the 2026 TikTok/Instagram platform framework. Invoked via a new `pipeline.py --strategy` flag that bypasses the existing studio path.

## Non-Goals (YAGNI)

- TikTok-specific output variant (platform = IG only)
- Multi-platform posting
- A/B testing logic (existing `--ab` flag covers)
- Web UI for human review (sidecar JSON is enough)
- Replacing existing `hook_specialist`/`copywriter`/`concept_picker` for `--studio` path

## Architecture

### Files

| Path | Status | Purpose |
|---|---|---|
| `studio/social_strategist.py` | NEW | Agent entry: `run(StrategyInput) -> dict` |
| `studio/prompts/strategist_system.py` | NEW | System prompt constant (verbatim 2026 framework + append-only schema directive) |
| `studio/client.py` | EDIT | Add `call_opus()` helper |
| `studio/settings.py` | EDIT | Add `STRATEGIST_MODEL` (default `claude-opus-4-7`), `STRATEGY_AUDIENCE` |
| `pipeline.py` | EDIT | Add `--strategy` flag + `_run_strategy()` branch |
| `tests/test_social_strategist.py` | NEW | Golden snapshot + schema + lint + fallback tests |

### Module internals

```python
# studio/social_strategist.py
_PREFIX = "STRAT"
_ROLE = "social_strategist"

@dataclass
class StrategyInput:
    trend: dict          # {headline, keywords, angle}
    quote_row: dict      # {text, attribution, source, row_number, mood}
    audience: str = "procrastinators/doomscrollers"

def run(inp: StrategyInput) -> dict:
    raw = client.call_opus(
        role=_ROLE, prefix=_PREFIX,
        system=SYSTEM_PROMPT,
        user=_build_user_msg(inp),
        schema=QuoteData, temperature=0.7, max_tokens=2000,
    )
    creative = QuoteData.from_dict(raw)
    _validate(creative)          # hashtag count, hook length
    _linter(creative["caption"]) # engagement-bait regex
    return creative
```

### `studio/prompts/strategist_system.py`

- Exports `SYSTEM_PROMPT: str`
- Contains the 2026 framework verbatim (paste from user request)
- Appends ONE directive: `Output must be valid JSON matching QuoteData schema. Hook ≤ 12 words. 3-5 hashtags. No engagement-bait. No PII.`
- No edits to the body of the framework — kept auditable

### Extended `QuoteData` schema (in `studio/types.py`)

Existing `--content` fields: `hook, bridge?, quote, cta, caption, hashtags, mood, attribution, audience, row_number`.

**Two new fields added:**
- `music_track_id: str | None` — Jamendo track from `music_director.pick()`. `None` if music unavailable → silent reel.
- `flux_prompt: str | None` — FLUX render prompt from `prompts/architect.run()`. `None` if unavailable → deterministic fallback prompt.

Both fields are optional in the schema; existing `--content` path that doesn't supply them falls back to current generators (existing behavior preserved).

## Run order on `--strategy`

```
1. trend_scout.run()              Sonnet  → {headline, keywords, angle}
2. _match_quote(keywords)         deterministic, in pipeline.py → quote_row
3. social_strategist.run()        Opus    → {hook, bridge?, quote, cta, caption, hashtags, mood, attribution, audience, row_number}
4. music_director.pick(mood)      Sonnet  → track_id
5. prompt_architect.run(...)      Sonnet  → FLUX prompt
6. assemble QuoteData JSON        Python — adds music_track_id, flux_prompt
7. pipeline._render_via_content() existing render path, with extended schema
```

`_match_quote()` lives in `pipeline.py` as a private helper. It scores each excel quote row against `trend["keywords"]` using simple keyword overlap + mood-fit bonus. Returns highest-scoring row or `None` if no row scores above threshold (default 0.2). Implementation: 20-line function, no LLM.

Cost ceiling per run: **1 Opus call + 3 Sonnet calls** (~$0.55-1.05).

## Data flow

```python
def _run_strategy(self):
    trend = self.studio.trend_scout.run()
    if not trend:
        return self._fallback_to_studio("--strategy: no trend")

    quote_row = self._match_quote(trend["keywords"])
    if not quote_row:
        return self._fallback_to_studio("--strategy: no quote match")

    creative = self.studio.social_strategist.run(StrategyInput(trend, quote_row))
    music = self.studio.music_director.pick(mood=creative["mood"], trend_keywords=trend["keywords"])
    flux_prompt = self.studio.prompt_architect.run(quote=creative["quote"], mood=creative["mood"], style="photorealism_rig")

    quote_data = {**creative, "music_track_id": music["track_id"], "flux_prompt": flux_prompt, "row_number": quote_row["row_number"]}
    return self._render_via_content(quote_data)
```

## Error handling

Every optional stage wraps in try/except → fallback. Never crash a reel.

| Stage | Failure → fallback |
|---|---|
| `trend_scout` empty/error | Use evergreen philosophy trend pool (Marcus Aurelius morning pages, etc.) |
| `excel.match_topic` no row | Pick highest-momentum quote regardless of trend. Log `strategy.no_trend_match`. |
| `social_strategist` Opus call fails | Retry once with Sonnet fallback (degraded mode, same prompt). Try/except → studio fallback. |
| `social_strategist` invalid schema | Reject, retry once with `temperature=0`. If still bad → studio fallback. |
| `social_strategist` hashtag count violated | Post-process clamp via `src/content/hashtag_pool.py` (existing) |
| `social_strategist` caption has engagement-bait | Linter rejects → retry once with explicit forbid. If still bad → strip via regex. |
| `music_director` fails | Skip music, render silent reel |
| `prompt_architect` fails | Deterministic FLUX prompt from quote + mood template |

**Safety gates (NEVER bypass):**
- Trend topic through existing `is_unsafe` keyword denylist (`trend_scout.py`)
- Bridge content inherits existing `prompt_safety_gate`
- Caption PII scan → Telegram/Slack alert (existing)

## Testing

`tests/test_social_strategist.py`:

| Test | Asserts |
|---|---|
| `test_golden_snapshot` | Same input → stable JSON (mark with `--snapshot-update`) |
| `test_schema_validation` | Output matches `QuoteData` dataclass |
| `test_hashtag_count` | Always 3-5 hashtags |
| `test_no_engagement_bait` | Regex rejects "like if", "comment below" |
| `test_hook_length` | Each hook ≤ 12 words |
| `test_bridge_optional` | Bridge present iff trend warrants |
| `test_fallback_trend_empty` | `trend_scout []` → uses evergreen pool |
| `test_fallback_opus_fail` | Opus error → Sonnet retry → studio fallback |
| `test_cost_ceiling` | Mock client → ≤ 1 Opus + ≤ 3 Sonnet calls |

CI: `pytest` run. Mock `client.call_opus()` to avoid $$ on every test.

## Rollout

1. Add modules + tests → CI green
2. Manual dry-run on 5 trending topics → human reviews output JSON
3. Replace one `--studio` slot with `--strategy` for 7 days
4. Compare engagement metrics (saves, shares, watch-time) vs same slot week prior
5. Lift → expand to all slots. Flat → keep both paths, document trade-off.

## Configuration

`studio/settings.py`:

```python
STRATEGIST_MODEL = os.getenv("STRATEGIST_MODEL", "claude-opus-4-7")
STRATEGY_AUDIENCE = os.getenv("STRATEGY_AUDIENCE", "procrastinators and doomscrollers who feel stuck")
```

`pipeline.py`:

```python
parser.add_argument("--strategy", action="store_true",
                    help="Trend-led IG content via Opus social_strategist. Bypasses studio.")
```

## Risks

- **Cost**: ~7× `--studio` run. Mitigated by ROI measurement in rollout step 4.
- **Latency**: Opus 5-10s vs studio parallel ~3s. Single call, no parallel. Acceptable.
- **Prompt drift**: System prompt is 2026-current. Re-evaluate annually or on platform shift.

## Related

- `docs/VIRAL_OPTIMIZATION_BRIEF.md` — already in-progress 100-point framework (overlap)
- `docs/VIRAL_STRATEGY_2026.md` — same domain
- `studio/trend_scout.py`, `studio/music_director.py`, `studio/prompts/architect.py` — sub-agents reused
- `pipeline.py --content <json>` — output schema reused (downstream render path)