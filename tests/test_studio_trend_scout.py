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
