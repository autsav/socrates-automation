import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from studio import analyst, settings
from studio.types import PerformanceBrief


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def call(self, *a, **k):
        self.calls += 1
        return self.payload


def _payload():
    return {"generated_at": "2026-06-23T00:00:00", "sample_size": 10,
            "window_days": 90, "top_hooks": [], "top_topics": [], "top_moods": [],
            "best_formats": {}, "best_slots": {}, "dying": [], "headline": "ok"}


@pytest.fixture(autouse=True)
def _stub_aggregate(monkeypatch):
    monkeypatch.setattr(analyst.data_store, "aggregate_performance",
                        lambda *a, **k: {"sample_size": 0})
    yield


def test_build_prompt_includes_stats():
    prefix, role = analyst.build_prompt({"sample_size": 42})
    assert "42" in prefix
    assert "analyst" in role.lower() or "performancebrief" in role.lower()


def test_parse_response():
    b = analyst.parse_response(_payload())
    assert isinstance(b, PerformanceBrief) and b.sample_size == 10


def test_get_or_build_writes_cache(tmp_path):
    settings.PERF_BRIEF_PATH = tmp_path / "perf.json"
    c = _FakeClient(_payload())
    b = analyst.get_or_build_brief(c)
    assert b.headline == "ok" and settings.PERF_BRIEF_PATH.exists()


def test_get_or_build_uses_fresh_cache(tmp_path):
    settings.PERF_BRIEF_PATH = tmp_path / "perf.json"
    settings.PERF_BRIEF_PATH.write_text(json.dumps(
        {**_payload(), "generated_at": datetime.utcnow().isoformat(),
         "headline": "cached"}))
    c = _FakeClient(_payload())
    b = analyst.get_or_build_brief(c, now=datetime.utcnow())
    assert b.headline == "cached" and c.calls == 0


def test_stale_cache_triggers_rebuild(tmp_path):
    settings.PERF_BRIEF_PATH = tmp_path / "perf.json"
    old = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    settings.PERF_BRIEF_PATH.write_text(json.dumps(
        {**_payload(), "generated_at": old, "headline": "stale"}))
    c = _FakeClient({**_payload(), "headline": "rebuilt"})
    b = analyst.get_or_build_brief(c, now=datetime.utcnow())
    assert b.headline == "rebuilt" and c.calls == 1
