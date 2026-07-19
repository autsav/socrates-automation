"""Every managed agent must load its prompt via prompt_store, so a promoted
challenger actually changes generation (critique B3: unwired agents made
approvals silent no-ops)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import studio.copywriter as copywriter
import studio.director as director
import studio.trend_scout as trend_scout
import studio.music_director as music_director
from src.optimizer import prompt_store, assets


class _FakeClient:
    def call(self, role, prefix, role_system, user, schema):
        # Return minimal schema-shaped data so from_dict doesn't choke; the test
        # only cares which prompt key was requested, captured via the spy below.
        return {"concepts": []} if "concepts" in str(schema) else {}


def _spy(monkeypatch):
    seen = []
    real = prompt_store.get

    def fake_get(key, default, *a, **k):
        seen.append(key)
        return default

    for mod in (copywriter, director, trend_scout, music_director):
        monkeypatch.setattr(mod.prompt_store, "get", fake_get)
    return seen


class _Brief:
    def to_dict(self):
        return {"quote": "q", "audience": "a"}


class _Perf:
    def to_dict(self):
        return {}


def test_director_loads_prompt_via_store(monkeypatch):
    seen = _spy(monkeypatch)
    director.build_prompt(_Perf(), _Brief(), [])
    assert "prompt.director.role" in seen


def test_copywriter_draft_loads_prompt_via_store(monkeypatch):
    seen = _spy(monkeypatch)
    copywriter.draft(_FakeClient(), _Perf(), _Brief(), n=1)
    assert "prompt.copywriter.draft" in seen


def test_trend_scout_loads_prompt_via_store(monkeypatch):
    seen = _spy(monkeypatch)

    class _TC:
        def call(self, *a, **k):
            return {"used": False}
    trend_scout.pick_hook(_TC(), [], {"quote": "q"})
    assert "prompt.trend_scout.role" in seen


def test_music_director_query_loads_prompt_via_store(monkeypatch):
    seen = _spy(monkeypatch)

    class _MC:
        def call(self, *a, **k):
            return {"search_query": "calm piano", "energy": "low",
                    "bpm_range": [60, 80], "instruments": ["piano"], "avoid": ["drums"]}
    music_director.compose_query(_MC(), {"quote": "q", "mood": "calm"})
    assert "prompt.music_director.query" in seen


def test_all_managed_keys_are_loaded_by_some_agent(monkeypatch):
    # Guard: every registered key must be one an agent actually reads at runtime.
    keys = {m["key"] for m in assets.MANAGED_PROMPTS}
    assert keys == {
        "prompt.strategist.role", "prompt.strategist.prefix",
        "prompt.copywriter.draft", "prompt.copywriter.revise",
        "prompt.director.role", "prompt.trend_scout.role",
        "prompt.music_director.query", "prompt.music_director.rank",
        "prompt.story_writer.role",
    }