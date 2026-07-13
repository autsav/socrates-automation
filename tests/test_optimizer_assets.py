import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import assets, registry, prompt_store
import studio.strategist as strat


def test_managed_prompts_include_strategist():
    keys = {m["key"] for m in assets.MANAGED_PROMPTS}
    assert "prompt.strategist.role" in keys


def test_iter_managed_seeds_and_returns_text(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    got = assets.iter_managed(db)
    keys = {g["key"] for g in got}
    assert "prompt.strategist.role" in keys
    for g in got:
        assert isinstance(g["champion_text"], str) and g["champion_text"]


def test_strategist_role_uses_prompt_store(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    prompt_store.get("prompt.strategist.role", strat._ROLE_DEFAULT, db)  # seed
    cid = registry.add_version("prompt.strategist.role",
                               "NEW ROLE slot={slot} recent={recent} pool={pool}",
                               "critic", "r", 0.1, db_path=db)
    registry.promote(cid, db)
    role = strat.build_role(slot=1, recent="x", pool="y", db_path=db)
    assert "NEW ROLE" in role
