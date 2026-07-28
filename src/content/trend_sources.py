"""Trend sources for the Trend Scout — headless, CI-safe, graceful.

Google Trends (via optional pytrends) and GNews headlines. Every function
degrades to [] on any error so a reel never fails for lack of a trend.
"""

from src.utils.logger import get_logger
logger = get_logger(__name__)

import re

import requests

GNEWS_API = "https://gnews.io/api/v4/top-headlines"
GNEWS_SEARCH = "https://gnews.io/api/v4/search"

# Theme queries that bridge reliably to Stoic/Socratic frames — far better
# newsjack candidates than generic top-headlines, much of which the safety
# denylist filters out anyway. Each query targets a behavior/culture the
# philosophy can genuinely reframe (the trend_scout "philosophy-bridge test").
_BRIDGE_QUERIES = (
    "burnout OR overwork OR hustle",
    "procrastination OR discipline OR habit",
    "social media OR screen time OR scrolling",
    "loneliness OR dating apps OR relationships",
    "purpose OR meaning OR career change",
    "AI productivity OR attention OR focus",
)

# Deterministic safety backstop (defense-in-depth on top of the agent's prompt
# rules): topics/hooks containing any of these whole words are treated as unsafe
# for a stoic-philosophy brand and dropped / forced to the evergreen hook.
# Whole-word matching (\b) avoids false positives like war->warrior/warm/reward.
_UNSAFE_TERMS = (
    # death / violence
    "killed", "killing", "kills", "dead", "death", "deaths", "murder", "murdered",
    "shooting", "shooter", "shot", "stabbing", "stabbed", "massacre", "suicide",
    "homicide", "gunman", "assassinated",
    # war / conflict
    "war", "warfare", "invasion", "invaded", "airstrike", "airstrikes", "missile",
    "missiles", "bombing", "bombed", "troops", "hostage", "hostages", "genocide",
    "terror", "terrorist", "terrorism", "militants", "gaza", "ukraine", "israel", "hamas",
    # hard politics
    "election", "elections", "president", "presidential", "senate", "congress",
    "parliament", "republican", "democrat", "democrats", "trump", "biden", "putin",
    "impeach", "coup",
    # disaster
    "earthquake", "hurricane", "wildfire", "wildfires", "flood", "floods", "tornado",
    "disaster", "evacuation", "evacuated", "crash", "crashed", "derailment", "deadly",
    # crime / legal
    "arrested", "arrest", "assault", "rape", "raped", "abuse", "lawsuit", "indicted",
    "charged", "verdict", "guilty", "fraud", "scandal",
    # medical / tragedy
    "cancer", "outbreak", "pandemic", "overdose", "dies", "died", "victim", "victims",
    "tragedy", "funeral", "mourning", "epidemic",
)

_UNSAFE_RE = re.compile(r"\b(" + "|".join(re.escape(t) for t in _UNSAFE_TERMS) + r")\b",
                        re.IGNORECASE)


def is_unsafe(text) -> bool:
    """True if `text` contains an unsafe whole word (see _UNSAFE_TERMS). Safe on
    empty/None input."""
    if not text:
        return False
    return _UNSAFE_RE.search(str(text)) is not None


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
        logger.warning(f"  [trends] google_trends unavailable ({type(e).__name__}) — skipping")
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
        return [(a["title"], a.get("publishedAt")) for a in r.json().get("articles", [])
                if a.get("title")]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"  [trends] gnews unavailable ({e}) — skipping")
        return []


def gnews_theme_headlines(api_key, limit=10):
    """GNews /search with theme queries that bridge to Stoic frames.

    Generic top-headlines mostly fail the philosophy-bridge test (or hit the
    safety denylist). Theme-targeted search returns articles the trend_scout
    can actually bridge, so fewer `used=false` rejections and more newsjack
    reels ship. [] on missing key or any error; never raises."""
    if not api_key:
        return []
    out = []
    for q in _BRIDGE_QUERIES:
        try:
            r = requests.get(GNEWS_SEARCH, params={
                "apikey": api_key, "lang": "en", "max": 4, "q": q,
                "in": "title,description",
            }, timeout=15)
            r.raise_for_status()
            for a in r.json().get("articles", []):
                if a.get("title"):
                    out.append((a["title"], a.get("publishedAt")))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"  [trends] gnews theme '{q}' unavailable ({e}) — skipping")
            continue
    return out[:limit]


# Trend -> mode classifier. A trend about a HABIT/behavior people are doing
# (a challenge, an app, a trend-on-tiktok) roasts cleanly (roast the habit the
# trend reveals). A trend about an EVENT/phenomenon happening to people (a
# study, a report, prices) lands as a Socratic verdict. Falls back to verdict
# (the safer, more flexible newsjack) when ambiguous.
_HABIT_CUES = re.compile(
    r"\b(trend|challenge|#\w+|going viral|everyone is|people are|app|hack|"
    r"habit|routine|tiktok|reels|scrolling|posting)\b", re.I)
_EVENT_CUES = re.compile(
    r"\b(report|study|survey|data|shows|reveals|says|announces|launches|"
    r"prices|crash|surge|drops|warns)\b", re.I)


def classify_trend_mode(topic: str) -> str:
    """Map a trending topic to the controversy mode that fits it best.

    'roast' for behavior/habit trends (roast the habit the trend reveals);
    'verdict' for event/phenomenon trends (Socrates judges the event);
    'verdict' as the safe fallback for ambiguous topics.
    """
    t = topic or ""
    if _HABIT_CUES.search(t) and not _EVENT_CUES.search(t):
        return "roast"
    return "verdict"


def fetch_trends(cfg, limit=20):
    """Merge Google Trends + GNews + Reddit into a deduped [{topic, source}] list."""
    out, seen = [], set()
    for topic in google_trends(15):
        k = (topic or "").strip().lower()
        if k and k not in seen and not is_unsafe(topic):
            seen.add(k)
            out.append({"topic": topic, "source": "google_trends"})
    for item in gnews_headlines(getattr(cfg, "GNEWS_API_KEY", ""), 10):
        title, published_at = item if isinstance(item, tuple) else (item, None)
        k = (title or "").strip().lower()
        if k and k not in seen and not is_unsafe(title):
            seen.add(k)
            out.append({"topic": title, "source": "gnews", "published_at": published_at})
    # Theme-targeted GNews search — bridges far better than generic headlines.
    for item in gnews_theme_headlines(getattr(cfg, "GNEWS_API_KEY", ""), 10):
        title, published_at = item if isinstance(item, tuple) else (item, None)
        k = (title or "").strip().lower()
        if k and k not in seen and not is_unsafe(title):
            seen.add(k)
            out.append({"topic": title, "source": "gnews_theme", "published_at": published_at})
    # Reddit trends — philosophy/stoicism communities
    try:
        from src.content.reddit_trends import reddit_trending_for_socrates
        for item in reddit_trending_for_socrates(10):
            k = (item["topic"] or "").strip().lower()
            if k and k not in seen and not is_unsafe(item["topic"]):
                seen.add(k)
                out.append(item)
    except Exception:
        pass  # Reddit unavailable — never break the pipeline
    # Recency weighting (recipe #9): trend-jacking works inside ~24h. Fresh
    # timestamped candidates first, older last; undated keep insertion order.
    def _recency_key(c):
        ts = c.get("published_at")
        if not ts:
            return 1  # undated: middle
        from datetime import datetime, timezone, timedelta
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return 0 if datetime.now(timezone.utc) - dt <= timedelta(hours=24) else 2
        except ValueError:
            return 1
    out.sort(key=_recency_key)
    return out[:limit]
