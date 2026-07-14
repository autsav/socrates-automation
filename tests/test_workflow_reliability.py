import subprocess
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text()


def test_analytics_uses_force_add():
    assert "git add -f data/pipeline.db" in _read(".github/workflows/analytics.yml")


def test_both_workflows_have_write_permission():
    for wf in (".github/workflows/analytics.yml", ".github/workflows/daily_post.yml"):
        t = _read(wf)
        assert "permissions:" in t and "contents: write" in t, f"{wf} missing write permission"


def test_daily_post_fails_loudly_on_missing_db():
    t = _read(".github/workflows/daily_post.yml")
    assert "data/pipeline.db missing" in t and "exit 1" in t


def test_gitignore_negates_pipeline_db():
    assert "!data/pipeline.db" in _read(".gitignore")


def test_pipeline_db_is_tracked():
    out = subprocess.run(
        ["git", "ls-files", "data/pipeline.db"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    assert out == "data/pipeline.db", "data/pipeline.db must be tracked in git"


def test_committed_db_has_no_token():
    conn = sqlite3.connect(str(ROOT / "data" / "pipeline.db"))
    try:
        n = conn.execute("SELECT count(*) FROM token_state").fetchone()[0]
    finally:
        conn.close()
    assert n == 0, "committed pipeline.db must not contain a token (secret leak)"


def test_committed_db_has_no_token_shaped_values_anywhere():
    # C2: don't only trust the token_state row-count — scan every TEXT column in
    # every table for a Meta-token-shaped literal, so a token cached elsewhere
    # (a JSON blob, a stray column) still trips the guard.
    conn = sqlite3.connect(str(ROOT / "data" / "pipeline.db"))
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        hits = []
        for t in tables:
            cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})")]
            for row in conn.execute(f"SELECT * FROM {t}"):
                for val in row:
                    if isinstance(val, str) and (
                        val.startswith(("EAA", "EAAG")) or (len(val) > 100 and "|" in val)
                    ):
                        hits.append((t, val[:12] + "…"))
    finally:
        conn.close()
    assert not hits, f"token-shaped value(s) found in committed DB: {hits}"


def test_scrub_committed_tokens_clears_meta(tmp_path, monkeypatch):
    from src.core import data_store
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db)
    data_store.init_db()
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT OR REPLACE INTO token_state (service, token, expires_at) "
                 "VALUES ('meta','EAAsecret','2030-01-01 00:00:00')")
    conn.commit()
    conn.close()
    data_store.scrub_committed_tokens(db)
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT count(*) FROM token_state WHERE service='meta'").fetchone()[0]
    conn.close()
    assert n == 0


def test_workflows_scrub_token_before_committing_db():
    for wf in (".github/workflows/analytics.yml", ".github/workflows/daily_post.yml"):
        t = _read(wf)
        i_scrub = t.find("DELETE FROM token_state")
        i_add = t.find("git add -f data/pipeline.db")
        assert i_scrub != -1, f"{wf} must scrub token_state before committing the DB"
        assert i_add != -1 and i_scrub < i_add, f"{wf}: token scrub must precede git add -f"


def test_daily_post_uses_remotion_for_pov():
    t = _read(".github/workflows/daily_post.yml")
    assert "python pipeline.py --manual --remotion" in t
    assert "actions/setup-node" in t
    assert "npm --prefix remotion ci" in t


def test_edge_tts_in_requirements():
    assert "edge-tts" in _read("requirements.txt"), "edge-tts must be a dependency so CI can generate voiceover"
