import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, prompt_store


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    return p


def test_get_seeds_and_returns_default(db):
    out = prompt_store.get("prompt.x", "DEFAULT", db)
    assert out == "DEFAULT"
    assert registry.get_champion("prompt.x", db)["value"] == "DEFAULT"


def test_get_returns_promoted_champion(db):
    prompt_store.get("prompt.x", "DEFAULT", db)          # seed v1
    cid = registry.add_version("prompt.x", "IMPROVED", "critic", "why", 0.2, db_path=db)
    registry.promote(cid, db)
    assert prompt_store.get("prompt.x", "DEFAULT", db) == "IMPROVED"


def test_get_never_raises_on_bad_db(tmp_path):
    bad = tmp_path / "nonexistent_dir" / "t.db"   # parent missing
    assert prompt_store.get("k", "FALLBACK", bad) == "FALLBACK"
