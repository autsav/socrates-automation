import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, experiments


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    registry.register_asset("k", "prompt", "A", p)
    return p


def _open(db):
    champ = registry.get_champion("k", db)
    chal = registry.add_version("k", "B", "critic", "r", 0.1, db_path=db)
    return experiments.open_experiment("k", champ["id"], chal, db_path=db), champ["id"], chal


def test_open_and_get(db):
    eid, _, _ = _open(db)
    assert experiments.get_open_experiment("k", db)["id"] == eid


def test_insufficient_samples(db):
    eid, _, _ = _open(db)
    res = experiments.evaluate(eid, {"champion": [0.1], "challenger": [0.2]}, min_samples=8, db_path=db)
    assert res["decision"] == "insufficient"


def test_promote_when_challenger_wins(db):
    eid, _, chal = _open(db)
    res = experiments.evaluate(
        eid,
        {"champion": [0.10] * 8, "challenger": [0.30] * 8},
        min_samples=8, margin=0.05, db_path=db,
    )
    assert res["decision"] == "promote"
    assert experiments.get_open_experiment("k", db) is None  # closed


def test_retire_when_challenger_loses(db):
    eid, _, chal = _open(db)
    res = experiments.evaluate(
        eid,
        {"champion": [0.30] * 8, "challenger": [0.10] * 8},
        min_samples=8, margin=0.05, db_path=db,
    )
    assert res["decision"] == "retire"


def test_expire_stale_closes_old_open_experiments(db):
    from datetime import datetime, timedelta
    eid, _, chal = _open(db)
    # 20 days later, TTL 14 → expired
    future = datetime.utcnow() + timedelta(days=20)
    expired = experiments.expire_stale(max_age_days=14, db_path=db, now=future)
    assert eid in expired
    assert experiments.get_open_experiment("k", db) is None          # asset reopened
    assert registry.get_version(chal, db)["status"] == "retired"


def test_expire_stale_leaves_fresh_experiments(db):
    eid, _, _ = _open(db)
    expired = experiments.expire_stale(max_age_days=14, db_path=db)   # now=utcnow → fresh
    assert expired == []
    assert experiments.get_open_experiment("k", db)["id"] == eid
