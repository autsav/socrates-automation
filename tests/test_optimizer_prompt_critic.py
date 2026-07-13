import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer.proposers import prompt_critic


class FakeClient:
    def __init__(self, resp, over=False):
        self._resp, self._over = resp, over
        self.calls = []

    def over_daily_ceiling(self):
        return self._over

    def call(self, role, prefix, role_system, user, schema):
        self.calls.append(role_system)
        return self._resp


def test_schema_sets_additional_properties_false():
    # StudioClient structured output rejects object schemas without this.
    assert prompt_critic.CRITIC_SCHEMA.get("additionalProperties") is False


def test_propose_returns_candidate():
    c = FakeClient({"candidate": "BETTER {slot}", "rationale": "tighter", "predicted_delta": 0.12})
    out = prompt_critic.propose(c, "prompt.strategist.role", "OLD {slot}", "perf: none yet")
    assert out["candidate"] == "BETTER {slot}"
    assert out["predicted_delta"] == 0.12
    assert "OLD {slot}" in c.calls[0]          # champion text is in the prompt
    assert "perf: none yet" in c.calls[0]      # perf context is in the prompt


def test_propose_none_when_over_ceiling():
    c = FakeClient({}, over=True)
    assert prompt_critic.propose(c, "k", "OLD", "ctx") is None


def test_propose_none_on_client_error():
    class Boom:
        def over_daily_ceiling(self):
            return False

        def call(self, *a, **k):
            raise RuntimeError("api down")

    assert prompt_critic.propose(Boom(), "k", "OLD", "ctx") is None
