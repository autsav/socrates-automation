import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from studio.client import StudioClient, StudioError
from studio import settings


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Usage:
    input_tokens = 1000
    output_tokens = 500
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _Resp:
    def __init__(self, text, stop="end_turn"):
        self.content = [_Block(text)]
        self.stop_reason = stop
        self.usage = _Usage()


class _FakeMessages:
    def __init__(self, resp):
        self._resp = resp
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._resp


class _FakeSDK:
    def __init__(self, resp):
        self.messages = _FakeMessages(resp)


@pytest.fixture(autouse=True)
def _isolate_spend(tmp_path):
    settings.SPEND_LOG_PATH = tmp_path / "spend.json"
    settings.DAILY_SPEND_CEILING_USD = 2.0
    yield


def test_call_parses_json():
    c = StudioClient("key", sdk=_FakeSDK(_Resp('{"top_pick": "c1"}')))
    out = c.call("director", "PREFIX", "ROLE", "USER", {"type": "object"})
    assert out == {"top_pick": "c1"}


def test_call_uses_correct_model_and_caches_prefix():
    fake = _FakeSDK(_Resp('{}'))
    c = StudioClient("key", sdk=fake)
    c.call("copywriter", "PREFIX", "ROLE", "USER", {"type": "object"})
    kw = fake.messages.kwargs
    assert kw["model"] == "claude-opus-4-8"
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    import json
    assert "budget_tokens" not in json.dumps(kw)


def test_refusal_raises():
    c = StudioClient("key", sdk=_FakeSDK(_Resp("", stop="refusal")))
    with pytest.raises(StudioError):
        c.call("director", "P", "R", "U", {"type": "object"})


def test_non_json_raises():
    c = StudioClient("key", sdk=_FakeSDK(_Resp("not json")))
    with pytest.raises(StudioError):
        c.call("director", "P", "R", "U", {"type": "object"})


def test_ceiling():
    c = StudioClient("key", sdk=_FakeSDK(_Resp('{}')))
    settings.DAILY_SPEND_CEILING_USD = 0.0
    c.call("copywriter", "P", "R", "U", {"type": "object"})
    assert c.over_daily_ceiling() is True
