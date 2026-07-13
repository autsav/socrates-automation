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
