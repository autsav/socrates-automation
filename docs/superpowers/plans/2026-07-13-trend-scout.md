# Trend Scout Implementation Plan (Sub-project NEW)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open reels with a live trending topic that bridges to a timeless Socratic quote — a studio agent fetches trends (Google Trends + GNews), picks the safest-bridging one, and sets `quote_data["hook"]` + `quote_data["bridge"]`, which feed Sub-project B's `--content`/BridgeScene path.

**Architecture:** `src/content/trend_sources.py` fetches trends headlessly (both sources degrade to `[]`); `studio/trend_scout.py` is a studio agent that picks + writes the hook/bridge with hard safety rules; `pipeline._apply_trend_scout` wires it into the content path, always-on when keys are present, self-gating via a `used:false` evergreen fallback.

**Tech Stack:** Python 3.11, `requests`, `pytrends` (optional/graceful), Anthropic SDK (studio agent), pytest.

## Global Constraints

- Python 3.11; run tests with `.venv/bin/python -m pytest`.
- Never crash a reel: every trend path degrades (missing key / empty trends / agent error / `used:false`) to the evergreen hook, logging only.
- `pytrends` is OPTIONAL — import it lazily; ImportError or its live 404 must degrade to `[]` (GNews carries the feature).
- GNews endpoint: `GET https://gnews.io/api/v4/top-headlines` with `apikey`, `lang=en`, `category=general`, `max`.
- SAFETY is mandatory in the agent prompt: no real-person factual claims; reject tragedy/death/disaster/war/hard-politics/violence/medical/financial/defamatory topics; prefer evergreen-adjacent themes; else `used:false`.
- Do NOT commit `data/pipeline.db`; if dirtied, `git checkout -- data/pipeline.db` first.
- Unrelated uncommitted artifacts exist (quotes.xlsx, remotion/public/*.mp3, reel-data.json) — never stage them. Only `git add` the files each task's commit step names.
- Full suite green EXCEPT the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures.

---

### Task 1: Config + role + dep

**Files:**
- Modify: `config.py` (`GNEWS_API_KEY` field), `.env.example`
- Modify: `studio/settings.py` (`trend_scout` role)
- Modify: `requirements.txt` (`pytrends`)
- Test: `tests/test_config_gnews.py`

**Interfaces:**
- Produces: `Config().GNEWS_API_KEY -> str`; `trend_scout` in `ROLE_MODELS`/`ROLE_EFFORT`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_gnews.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_exposes_gnews_key(monkeypatch):
    monkeypatch.setenv("GNEWS_API_KEY", "abc123")
    from config import Config
    assert Config().GNEWS_API_KEY == "abc123"


def test_trend_scout_role_registered():
    from studio import settings
    assert settings.ROLE_MODELS["trend_scout"]
    assert settings.ROLE_EFFORT["trend_scout"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config_gnews.py -v`
Expected: FAIL (`GNEWS_API_KEY` / `trend_scout` missing).

- [ ] **Step 3: Implement**

In `config.py`, add a class attr next to `JAMENDO_CLIENT_ID: str = ""`:
```python
    GNEWS_API_KEY: str = ""           # Optional — GNews headlines for Trend Scout
```
and the assignment next to `self.JAMENDO_CLIENT_ID = self._get_opt("JAMENDO_CLIENT_ID")`:
```python
        self.GNEWS_API_KEY           = self._get_opt("GNEWS_API_KEY")
```
In `.env.example`, under the Jamendo section:
```
# GNews API — https://gnews.io (free key), for the Trend Scout
GNEWS_API_KEY=your_gnews_api_key_here
```
In `studio/settings.py`, add to `ROLE_MODELS`:
```python
    "trend_scout":            "claude-sonnet-4-6",
```
and `ROLE_EFFORT`:
```python
    "trend_scout":            "medium",
```
In `requirements.txt`, add (near the audio/optional deps):
```
pytrends>=4.9.2  # Google Trends (optional; Trend Scout degrades to GNews if unavailable)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config_gnews.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add config.py .env.example studio/settings.py requirements.txt tests/test_config_gnews.py
git commit -m "feat(trend-scout): add GNEWS_API_KEY config + trend_scout role + pytrends dep"
```

---

### Task 2: `src/content/trend_sources.py`

**Files:**
- Create: `src/content/trend_sources.py`
- Test: `tests/test_trend_sources.py`

**Interfaces:**
- Produces: `google_trends(limit=15) -> list[str]`; `gnews_headlines(api_key, limit=10) -> list[str]`; `fetch_trends(cfg, limit=20) -> list[dict]` (`[{topic, source}]`, deduped).

- [ ] **Step 1: Write the failing test**

Create `tests/test_trend_sources.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content import trend_sources as ts


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_gnews_headlines_parses_titles(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        assert params["apikey"] == "KEY"
        return _Resp({"articles": [{"title": "A"}, {"title": "B"}, {"title": ""}]})
    monkeypatch.setattr(ts.requests, "get", fake_get)
    assert ts.gnews_headlines("KEY", limit=10) == ["A", "B"]


def test_gnews_headlines_no_key_or_error(monkeypatch):
    assert ts.gnews_headlines("", limit=10) == []
    monkeypatch.setattr(ts.requests, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("net")))
    assert ts.gnews_headlines("KEY") == []


def test_google_trends_degrades_gracefully(monkeypatch):
    # Force the internal fetch to raise (mimics pytrends 404 / ImportError).
    monkeypatch.setattr(ts, "_pytrends_daily", lambda limit: (_ for _ in ()).throw(RuntimeError("404")))
    assert ts.google_trends() == []


def test_fetch_trends_merges_and_dedupes(monkeypatch):
    monkeypatch.setattr(ts, "google_trends", lambda limit=15: ["Elon Musk", "AI layoffs"])
    monkeypatch.setattr(ts, "gnews_headlines", lambda key, limit=10: ["AI layoffs", "Fed rates"])

    class _Cfg: GNEWS_API_KEY = "KEY"
    out = ts.fetch_trends(_Cfg())
    topics = [c["topic"] for c in out]
    assert topics == ["Elon Musk", "AI layoffs", "Fed rates"]  # deduped, order preserved
    assert {c["source"] for c in out} == {"google_trends", "gnews"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_trend_sources.py -v`
Expected: FAIL (`ModuleNotFoundError: src.content.trend_sources`).

- [ ] **Step 3: Create the module**

Create `src/content/trend_sources.py`:

```python
"""Trend sources for the Trend Scout — headless, CI-safe, graceful.

Google Trends (via optional pytrends) and GNews headlines. Every function
degrades to [] on any error so a reel never fails for lack of a trend.
"""
import requests

GNEWS_API = "https://gnews.io/api/v4/top-headlines"


def _pytrends_daily(limit):
    """Actual pytrends call, isolated so it can be mocked. Lazy import so the
    module loads without pytrends installed."""
    from pytrends.request import TrendReq
    p = TrendReq(hl="en-US", tz=360)
    df = p.trending_searches(pn="united_states")
    return [str(row[0]) for row in df.head(limit).values.tolist()]


def google_trends(limit=15):
    """US daily trending searches. [] on ImportError / rate-limit / 404."""
    try:
        return _pytrends_daily(limit)
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        print(f"  [trends] google_trends unavailable ({type(e).__name__}) — skipping")
        return []


def gnews_headlines(api_key, limit=10):
    """GNews top headlines (titles). [] on missing key or any error."""
    if not api_key:
        return []
    try:
        r = requests.get(GNEWS_API, params={
            "apikey": api_key, "lang": "en", "category": "general", "max": limit,
        }, timeout=15)
        r.raise_for_status()
        return [a["title"] for a in r.json().get("articles", []) if a.get("title")]
    except Exception as e:  # noqa: BLE001
        print(f"  [trends] gnews unavailable ({e}) — skipping")
        return []


def fetch_trends(cfg, limit=20):
    """Merge Google Trends + GNews into a deduped [{topic, source}] list."""
    out, seen = [], set()
    for topic in google_trends(15):
        k = (topic or "").strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append({"topic": topic, "source": "google_trends"})
    for title in gnews_headlines(getattr(cfg, "GNEWS_API_KEY", ""), 10):
        k = (title or "").strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append({"topic": title, "source": "gnews"})
    return out[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_trend_sources.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add src/content/trend_sources.py tests/test_trend_sources.py
git commit -m "feat(trend-scout): trend_sources (Google Trends + GNews, graceful)"
```

---

### Task 3: TrendHook type + trend_scout agent

**Files:**
- Modify: `studio/types.py` (`TrendHook` + `TREND_HOOK_SCHEMA`)
- Create: `studio/trend_scout.py`
- Test: `tests/test_studio_trend_scout.py`

**Interfaces:**
- Produces: `TrendHook(used, topic, source, hook, bridge, rationale)` with `to_dict`/`from_dict`; `TREND_HOOK_SCHEMA`; `pick_hook(client, candidates, quote_ctx) -> TrendHook`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_studio_trend_scout.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import trend_scout as ts
from studio.types import TrendHook


class _SeqClient:
    def __init__(self, payloads): self.payloads = list(payloads); self.roles = []
    def call(self, role, *a, **k): self.roles.append(role); return self.payloads.pop(0)


def _candidates():
    return [{"topic": "AI layoffs", "source": "gnews"}, {"topic": "burnout", "source": "google_trends"}]


def _qctx():
    return {"quote": "Beware the barrenness of a busy life.", "theme": "dark_philosophical", "audience": "overwhelmed"}


def test_pick_hook_used(monkeypatch):
    client = _SeqClient([{"used": True, "topic": "AI layoffs", "source": "gnews",
                          "hook": "AI is quietly stealing your time.",
                          "bridge": "But Socrates named this trap.", "rationale": "bridges to busyness"}])
    th = ts.pick_hook(client, _candidates(), _qctx())
    assert isinstance(th, TrendHook)
    assert th.used and th.hook and th.bridge
    assert client.roles == ["trend_scout"]


def test_pick_hook_unused_when_nothing_safe():
    client = _SeqClient([{"used": False}])
    th = ts.pick_hook(client, _candidates(), _qctx())
    assert th.used is False
    assert th.hook == ""  # defaults
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_studio_trend_scout.py -v`
Expected: FAIL (`studio.trend_scout` / `TrendHook` missing).

- [ ] **Step 3: Add the type**

Append to `studio/types.py` (dataclass with the others, schema after `MUSIC_PICK_SCHEMA`):

```python
@dataclass
class TrendHook:
    used: bool
    topic: str = ""
    source: str = ""
    hook: str = ""
    bridge: str = ""
    rationale: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)
```

```python
TREND_HOOK_SCHEMA = _obj({
    "used": {"type": "boolean"},
    "topic": {"type": "string"},
    "source": {"type": "string"},
    "hook": {"type": "string"},
    "bridge": {"type": "string"},
    "rationale": {"type": "string"},
}, ["used"])
```

- [ ] **Step 4: Create the agent**

Create `studio/trend_scout.py`:

```python
"""Trend Scout agent — turns a live trending topic into a scroll-stopping hook
that bridges to a timeless Socratic quote. The trend is bait; the quote is the
payoff. Hard safety rules; returns used=false when nothing bridges safely."""
import json

from studio.types import TrendHook, TREND_HOOK_SCHEMA

_PREFIX = (
    "You are a social-media trend strategist for a stoic-philosophy Instagram "
    "account. You turn a trending topic into a scroll-stopping hook that bridges "
    "to a timeless Socratic quote — the trend is bait, the philosophy is the payoff."
)

_ROLE = (
    "Chosen quote / theme:\n{quote_ctx}\n"
    "Candidate trending topics (Google Trends + news headlines):\n{candidates}\n"
    "Pick the ONE topic that bridges most naturally to this quote's theme AND is "
    "brand-safe.\n"
    "SAFETY (hard rules): never claim a real person said or did a specific thing; "
    "REJECT tragedy, death, disaster, war, hard politics, violence, crime, medical "
    "or financial advice, and defamatory or protected-class angles. Prefer "
    "evergreen-adjacent topics (money, work, burnout, success, AI, habits, "
    "discipline, relationships, ambition). If NO candidate bridges cleanly and "
    "safely, set used=false.\n"
    "When used=true, also write: hook (5-12 words, formula-compliant, negative "
    "framing where apt, referencing the trend as bait) and bridge (the '…but 2,400 "
    "years ago Socrates already knew…' pivot connecting trend -> quote, using "
    "But/Therefore momentum). Set topic + source to the chosen candidate. "
    "Output a TrendHook as JSON only."
)


def pick_hook(client, candidates, quote_ctx) -> TrendHook:
    role = _ROLE.format(
        quote_ctx=json.dumps(quote_ctx, indent=2),
        candidates=json.dumps([c["topic"] for c in candidates], indent=2),
    )
    d = client.call("trend_scout", _PREFIX, role,
                    "Pick and write the trend hook now.", TREND_HOOK_SCHEMA)
    return TrendHook.from_dict(d)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_trend_scout.py tests/test_studio_types.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add studio/types.py studio/trend_scout.py tests/test_studio_trend_scout.py
git commit -m "feat(trend-scout): TrendHook type + trend_scout agent (safety-gated)"
```

---

### Task 4: Integration + injection guard + CI wiring

**Files:**
- Modify: `pipeline.py` (`_apply_trend_scout`, call it in `run_pipeline`; guard `_injected_content` file read)
- Modify: `.github/workflows/daily_post.yml` (add `GNEWS_API_KEY` env)
- Test: `tests/test_trend_scout_integration.py`

**Interfaces:**
- Consumes: `trend_sources.fetch_trends`, `trend_scout.pick_hook`, `StudioClient`.
- Produces: `_apply_trend_scout(cfg, quote_data) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_trend_scout_integration.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from studio.types import TrendHook


class _Cfg:
    GNEWS_API_KEY = "K"
    ANTHROPIC_API_KEY = "A"


def test_apply_trend_scout_sets_hook_and_bridge(monkeypatch):
    monkeypatch.setattr(pipeline, "_trend_fetch", lambda cfg: [{"topic": "AI layoffs", "source": "gnews"}])
    monkeypatch.setattr(pipeline, "_trend_pick",
                        lambda cfg, cands, qctx: TrendHook(used=True, topic="AI layoffs", source="gnews",
                                                           hook="AI is stealing your time.", bridge="But Socrates knew."))
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "mood": "dark_philosophical", "audience": "overwhelmed"})
    assert qd["hook"] == "AI is stealing your time."
    assert qd["bridge"] == "But Socrates knew."


def test_apply_trend_scout_unused_leaves_hook(monkeypatch):
    monkeypatch.setattr(pipeline, "_trend_fetch", lambda cfg: [{"topic": "x", "source": "gnews"}])
    monkeypatch.setattr(pipeline, "_trend_pick", lambda cfg, cands, qctx: TrendHook(used=False))
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "mood": "m"})
    assert "hook" not in qd or not qd.get("hook")
    assert not qd.get("bridge")


def test_apply_trend_scout_no_key_noop():
    class _C: GNEWS_API_KEY = ""; ANTHROPIC_API_KEY = "A"
    qd = pipeline._apply_trend_scout(_C(), {"quote": "q"})
    assert not qd.get("bridge")


def test_apply_trend_scout_skips_injected_bridge():
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "bridge": "already here"})
    assert qd["bridge"] == "already here"  # injected content not overridden
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_trend_scout_integration.py -v`
Expected: FAIL (`_apply_trend_scout` undefined).

- [ ] **Step 3: Implement `_apply_trend_scout` + thin seams**

Add to `pipeline.py` (near `_select_reel_music`). The `_trend_fetch`/`_trend_pick` seams keep the heavy imports lazy and make the function testable:

```python
def _trend_fetch(cfg):
    from src.content import trend_sources
    return trend_sources.fetch_trends(cfg)


def _trend_pick(cfg, candidates, quote_ctx):
    from studio.client import StudioClient
    from studio import trend_scout
    client = StudioClient(cfg.ANTHROPIC_API_KEY)
    if client.over_daily_ceiling():
        return None
    return trend_scout.pick_hook(client, candidates, quote_ctx)


def _apply_trend_scout(cfg, quote_data):
    """Source a trending hook+bridge and set quote_data['hook']/['bridge'] when
    GNEWS_API_KEY + ANTHROPIC_API_KEY are present. Skips injected content (already
    has a bridge). Never raises; unchanged on any failure or used=false."""
    if quote_data.get("bridge"):
        return quote_data
    if not (getattr(cfg, "GNEWS_API_KEY", "") and getattr(cfg, "ANTHROPIC_API_KEY", "")):
        return quote_data
    try:
        candidates = _trend_fetch(cfg)
        if not candidates:
            log.info("  [trend-scout] no trends available — evergreen hook")
            return quote_data
        qctx = {"quote": quote_data.get("quote", ""), "theme": quote_data.get("mood", ""),
                "audience": quote_data.get("audience", "")}
        th = _trend_pick(cfg, candidates, qctx)
        if th and th.used and th.hook:
            quote_data["hook"] = th.hook
            quote_data["bridge"] = th.bridge
            log.info(f"  [trend-scout] {th.source}:{th.topic[:40]!r} -> trending hook set")
        else:
            log.info("  [trend-scout] no safe bridge -> evergreen hook")
    except Exception as e:  # noqa: BLE001 - never crash a reel
        log.warning(f"  [trend-scout] unavailable ({e}) - evergreen")
    return quote_data
```

- [ ] **Step 4: Call it in `run_pipeline` + guard the injection read**

In `run_pipeline`, immediately AFTER the content stage sets `quote_data` and `mood` (after the injected/studio/legacy block, before "Phase 1: Inject viral engagement"), add:

```python
    quote_data = _apply_trend_scout(cfg, quote_data)
```

Guard the injected-content read (deferred from Sub-project B): wrap the injection branch so a missing/malformed `--content` file falls back to legacy instead of crashing. In the `if content:` branch, change:
```python
    if content:
        quote_data, mood = _injected_content(content, cfg)
        ...
```
to:
```python
    if content:
        try:
            quote_data, mood = _injected_content(content, cfg)
        except Exception as e:  # noqa: BLE001
            log.error(f"--content unreadable ({e}) — falling back to legacy")
            content = None
        else:
            studio_decision = None
            controversy = ""
            caption_variant = -1
```
(Setting `content = None` makes the existing `if not content and studio_decision is None:` legacy guard fire.)

- [ ] **Step 5: Wire the key into CI**

In `.github/workflows/daily_post.yml`, add to the `env:` block of the step(s) that run `pipeline.py` (alongside `JAMENDO_CLIENT_ID`):
```yaml
          GNEWS_API_KEY:          ${{ secrets.GNEWS_API_KEY }}
```
(Do NOT add it to the "Validate required secrets" list — it is optional.)

- [ ] **Step 6: Run tests + full suite**

Run: `.venv/bin/python -m pytest tests/test_trend_scout_integration.py -v`
Expected: PASS (4).
Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/daily_post.yml')); print('yaml OK')"`
Expected: `yaml OK`.
Run: `.venv/bin/python -m pytest -q`
Expected: only the 2 pre-existing `tests/test_reel_composer.py` ffmpeg failures. If `test_committed_db_has_no_token` fails, `git checkout -- data/pipeline.db` and re-run.

- [ ] **Step 7: Commit**

```bash
git add pipeline.py .github/workflows/daily_post.yml tests/test_trend_scout_integration.py
git commit -m "feat(trend-scout): wire into reel content path + CI; guard --content read"
```

---

## Notes for the implementer

- `_apply_trend_scout` runs for ALL reels but only sets a `bridge` (which needs Sub-project B's Remotion BridgeScene, already merged) on the POV/remotion path; for image/carousel formats the trending hook is set but no bridge scene exists — harmless.
- Google Trends currently 404s via pytrends (Google deprecated the endpoint); `google_trends` returns `[]` and GNews carries the feature. Do not treat the 404 as a bug — it is the designed graceful-skip.
- End-to-end manual check (needs `GNEWS_API_KEY` in `.env`, already present): `.venv/bin/python pipeline.py --remotion --dry-run 2>&1 | grep -i trend-scout` — expect a `[trend-scout] … trending hook set` or `no safe bridge` line.
