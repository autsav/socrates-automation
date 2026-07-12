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
