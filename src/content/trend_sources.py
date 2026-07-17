"""Trend sources for the Trend Scout — headless, CI-safe, graceful.

Google Trends (via optional pytrends) and GNews headlines. Every function
degrades to [] on any error so a reel never fails for lack of a trend.
"""
import re

import requests

GNEWS_API = "https://gnews.io/api/v4/top-headlines"

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
    """Merge Google Trends + GNews + Reddit into a deduped [{topic, source}] list."""
    out, seen = [], set()
    for topic in google_trends(15):
        k = (topic or "").strip().lower()
        if k and k not in seen and not is_unsafe(topic):
            seen.add(k)
            out.append({"topic": topic, "source": "google_trends"})
    for title in gnews_headlines(getattr(cfg, "GNEWS_API_KEY", ""), 10):
        k = (title or "").strip().lower()
        if k and k not in seen and not is_unsafe(title):
            seen.add(k)
            out.append({"topic": title, "source": "gnews"})
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
    return out[:limit]
