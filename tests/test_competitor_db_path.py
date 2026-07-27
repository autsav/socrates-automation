from pathlib import Path

from src.analytics import competitor


def test_db_path_resolves_to_repo_root():
    """competitor.DB_PATH must match the repo-root data/pipeline.db convention."""
    expected = Path(__file__).parent.parent / "data" / "pipeline.db"
    assert competitor.DB_PATH == expected, (
        f"DB_PATH {competitor.DB_PATH} != expected {expected}"
    )