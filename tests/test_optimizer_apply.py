import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, experiments, loop


def _setup(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    registry.register_asset("k", "prompt", "A {x}", db)
    champ = registry.get_champion("k", db)
    cid = registry.add_version("k", "B {x}", "critic", "r", 0.2, db_path=db)
    experiments.open_experiment("k", champ["id"], cid, db_path=db)
    return db, cid


def test_apply_approve_promotes(tmp_path):
    db, cid = _setup(tmp_path)
    assert loop.apply_decision(cid, True, db) == "promoted"
    assert registry.get_champion("k", db)["value"] == "B {x}"
    assert experiments.get_open_experiment("k", db) is None


def test_apply_reject_retires(tmp_path):
    db, cid = _setup(tmp_path)
    assert loop.apply_decision(cid, False, db) == "rejected"
    assert registry.get_champion("k", db)["value"] == "A {x}"   # unchanged
    assert experiments.get_open_experiment("k", db) is None
