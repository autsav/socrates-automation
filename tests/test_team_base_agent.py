import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from team.base_agent import AgentError, BaseAgent


class _FlakyClient:
    """Fails the first `fail_count` calls, then returns `payload`."""

    def __init__(self, payload, fail_count=0, exc=ValueError):
        self.payload = payload
        self.fail_count = fail_count
        self.exc = exc
        self.calls = 0

    def call(self, role, shared_prefix, role_system, user_content, schema):
        self.calls += 1
        if self.calls <= self.fail_count:
            raise self.exc(f"boom {self.calls}")
        return self.payload


def _identity(d):
    return d


def test_succeeds_first_try_without_sleeping(monkeypatch):
    slept = []
    monkeypatch.setattr("team.base_agent.time.sleep", lambda s: slept.append(s))
    client = _FlakyClient({"ok": True}, fail_count=0)
    agent = BaseAgent(client)

    result = agent.call_with_retry("role", "prefix", "system", "user", {}, _identity)

    assert result == {"ok": True}
    assert client.calls == 1
    assert slept == []


def test_retries_and_succeeds_before_exhausting_retries(monkeypatch):
    slept = []
    monkeypatch.setattr("team.base_agent.time.sleep", lambda s: slept.append(s))
    client = _FlakyClient({"ok": True}, fail_count=2)
    agent = BaseAgent(client)
    agent.max_retries = 3
    agent.retry_delay = 1.0

    result = agent.call_with_retry("role", "prefix", "system", "user", {}, _identity)

    assert result == {"ok": True}
    assert client.calls == 3
    # exponential backoff: retry_delay * 2**(attempt-1) for attempts 1 and 2
    assert slept == [1.0, 2.0]


def test_raises_agent_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("team.base_agent.time.sleep", lambda s: None)
    client = _FlakyClient({"ok": True}, fail_count=99, exc=KeyError)
    agent = BaseAgent(client)
    agent.max_retries = 3

    with pytest.raises(AgentError) as exc_info:
        agent.call_with_retry("planner", "prefix", "system", "user", {}, _identity)

    assert client.calls == 3
    assert "planner" in str(exc_info.value)
    assert "3 attempts" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, KeyError)


def test_malformed_response_from_parse_fn_is_retried_too(monkeypatch):
    """A response that parses as JSON but is missing a required key must
    surface as a retried AgentError, not a bare KeyError escaping from
    inside a dataclass constructor."""
    monkeypatch.setattr("team.base_agent.time.sleep", lambda s: None)

    def _parse_requires_key(d):
        return d["missing_key"]

    client = _FlakyClient({"present": 1}, fail_count=0)
    agent = BaseAgent(client)
    agent.max_retries = 2

    with pytest.raises(AgentError):
        agent.call_with_retry("role", "prefix", "system", "user", {}, _parse_requires_key)

    assert client.calls == 2
