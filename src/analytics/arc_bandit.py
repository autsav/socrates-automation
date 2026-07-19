"""Thompson-sampling arc selection on sends-per-reach (spec 2.3).
A post is a 'hit' when its sends-per-reach beats the global median; each arc
gets Beta(1+hits, 1+misses). Deterministic per row (seeded RNG) so tests and
reruns reproduce. Below DATA_FLOOR scored posts -> None (static rotation)."""
import random
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "pipeline.db"
DATA_FLOOR = 20
ARCS = ("story", "weird", "classic", "question", "cold_open")


def _scores(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        return [(arc, shares / reach) for arc, shares, reach in con.execute(
            "SELECT p.arc, m.shares, m.reach FROM posts p "
            "JOIN post_metrics m ON p.post_id = m.post_id "
            "WHERE p.dry_run=0 AND p.arc IS NOT NULL AND m.reach >= 100")
            if reach]
    finally:
        con.close()


def pick(row_number, has_trend, db_path=DEFAULT_DB):
    try:
        scores = _scores(db_path)
        if len(scores) < DATA_FLOOR:
            return None
        med = sorted(s for _, s in scores)[len(scores) // 2]
        rng = random.Random(row_number or 0)
        best, best_draw = None, -1.0
        for arc in ARCS:
            hits = sum(1 for a, s in scores if a == arc and s >= med)
            miss = sum(1 for a, s in scores if a == arc and s < med)
            draw = rng.betavariate(1 + hits, 1 + miss)
            if draw > best_draw:
                best, best_draw = arc, draw
        return best
    except Exception:  # noqa: BLE001 - bandit failure -> static rotation
        return None
