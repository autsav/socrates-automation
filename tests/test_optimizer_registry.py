import sqlite3
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def test_register_seeds_champion_v1(db):
    vid = registry.register_asset("prompt.strategist.role", "prompt", "SEED TEXT", db)
    champ = registry.get_champion("prompt.strategist.role", db)
    assert champ["value"] == "SEED TEXT"
    assert champ["version_num"] == 1
    assert champ["status"] == "champion"
    assert champ["id"] == vid


def test_register_is_idempotent(db):
    v1 = registry.register_asset("k", "prompt", "A", db)
    v2 = registry.register_asset("k", "prompt", "DIFFERENT", db)
    assert v1 == v2
    assert registry.get_champion("k", db)["value"] == "A"  # seed not overwritten


def test_add_version_and_promote(db):
    registry.register_asset("k", "prompt", "A", db)
    cid = registry.add_version("k", "B", source="critic", rationale="tighter", predicted_delta=0.1, db_path=db)
    assert registry.get_champion("k", db)["value"] == "A"  # challenger not yet champion
    registry.promote(cid, db)
    champ = registry.get_champion("k", db)
    assert champ["value"] == "B"
    assert champ["version_num"] == 2
    con = sqlite3.connect(db)
    statuses = {r[0] for r in con.execute("select status from opt_versions where key='k'")}
    assert "retired" in statuses and "champion" in statuses


def test_get_champion_missing_returns_none(db):
    assert registry.get_champion("nope", db) is None
