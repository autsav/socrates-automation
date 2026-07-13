import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import loop, registry, experiments, assets


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def _good_propose(client, key, champ, perf):
    return {"candidate": champ + " (sharper)", "rationale": "tighter", "predicted_delta": 0.2}


def test_run_once_creates_proposals(db):
    props = loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=_good_propose)
    assert len(props) == len(assets.MANAGED_PROMPTS)
    keys = {p["key"] for p in props}
    assert "prompt.strategist.role" in keys
    assert experiments.get_open_experiment("prompt.strategist.role", db) is not None


def test_run_once_skips_open_experiments(db):
    loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=_good_propose)
    props2 = loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=_good_propose)
    assert props2 == []


def test_run_once_drops_guardrail_failures(db):
    def bad(client, key, champ, perf):
        return {"candidate": "no placeholders here", "rationale": "x", "predicted_delta": 0.5}
    props = loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=bad)
    assert all(p["key"] not in ("prompt.strategist.role", "prompt.strategist.prefix") for p in props)


def test_run_once_never_raises_on_propose_error(db):
    def boom(*a, **k):
        raise RuntimeError("x")
    assert loop.run_once(client=None, perf_context="none", db_path=db, propose_fn=boom) == []
