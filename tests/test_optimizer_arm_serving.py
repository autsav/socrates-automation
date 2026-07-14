"""A/B arm-serving: begin_run() makes get() serve the challenger on ~half of
runs (deterministic by seed), records which version was used, and end_run()
restores champion-only behavior. Opt-in — no begin_run() means champion always."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, experiments, prompt_store


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    registry.register_asset("prompt.strategist.role", "prompt", "CHAMP {x}", p)
    champ = registry.get_champion("prompt.strategist.role", p)["id"]
    chal = registry.add_version("prompt.strategist.role", "CHAL {x}", "critic", "r", 0.2, db_path=p)
    experiments.open_experiment("prompt.strategist.role", champ, chal, db_path=p)
    return p


def teardown_function():
    prompt_store.end_run()  # never leak arm context across tests


def test_no_run_context_serves_champion(db):
    assert prompt_store.get("prompt.strategist.role", "DEF", db) == "CHAMP {x}"


def test_begin_run_can_serve_challenger(db):
    # Find a seed that lands on the challenger arm, prove get() serves it.
    served_challenger = False
    for seed in range(10):
        prompt_store.begin_run(seed, db)
        if prompt_store.get("prompt.strategist.role", "DEF", db) == "CHAL {x}":
            served_challenger = True
            assert prompt_store.run_versions()["prompt.strategist.role"] is not None
            break
        prompt_store.end_run()
    assert served_challenger, "no seed served the challenger arm"


def test_both_arms_reachable_across_seeds(db):
    seen = set()
    for seed in range(12):
        prompt_store.begin_run(seed, db)
        seen.add(prompt_store.get("prompt.strategist.role", "DEF", db))
        prompt_store.end_run()
    assert seen == {"CHAMP {x}", "CHAL {x}"}   # both arms served


def test_end_run_restores_champion(db):
    prompt_store.begin_run(0, db)
    prompt_store.end_run()
    assert prompt_store.get("prompt.strategist.role", "DEF", db) == "CHAMP {x}"
    assert prompt_store.run_versions() == {}
