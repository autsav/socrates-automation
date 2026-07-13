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
