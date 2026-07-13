"""Optimizable asset registry — versioned prompts/policies/weights in SQLite.

Each asset has a champion version (active) + history. Additive migrations only,
matching src/core/data_store.py conventions. Never raises on read paths."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"


def _connect(db_path):
    return sqlite3.connect(str(db_path))


def init_optimizer_db(db_path=DB_PATH):
    con = _connect(db_path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS opt_assets (
                key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                champion_version_id INTEGER,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS opt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                version_num INTEGER NOT NULL,
                value_json TEXT NOT NULL,
                source TEXT,
                rationale TEXT,
                predicted_delta REAL DEFAULT 0.0,
                status TEXT DEFAULT 'candidate',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS opt_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                champion_version_id INTEGER,
                challenger_version_id INTEGER,
                metric TEXT,
                status TEXT DEFAULT 'open',
                opened_at TEXT,
                closed_at TEXT,
                result_json TEXT
            );
            """
        )
        con.commit()
    finally:
        con.close()


def _row_to_version(r):
    if r is None:
        return None
    return {
        "id": r[0], "key": r[1], "version_num": r[2], "value": r[3],
        "source": r[4], "rationale": r[5], "predicted_delta": r[6], "status": r[7],
    }


def register_asset(key, kind, seed_value, db_path=DB_PATH):
    init_optimizer_db(db_path)
    con = _connect(db_path)
    try:
        existing = con.execute(
            "SELECT champion_version_id FROM opt_assets WHERE key=?", (key,)
        ).fetchone()
        if existing and existing[0] is not None:
            return existing[0]
        now = datetime.utcnow().isoformat()
        cur = con.execute(
            "INSERT INTO opt_versions (key, version_num, value_json, source, rationale, "
            "predicted_delta, status, created_at) VALUES (?,1,?,?,?,0.0,'champion',?)",
            (key, seed_value, "seed", "seed v1", now),
        )
        vid = cur.lastrowid
        con.execute(
            "INSERT OR REPLACE INTO opt_assets (key, kind, champion_version_id, created_at) "
            "VALUES (?,?,?,?)",
            (key, kind, vid, now),
        )
        con.commit()
        return vid
    finally:
        con.close()


def add_version(key, value, source, rationale, predicted_delta, status="challenger", db_path=DB_PATH):
    con = _connect(db_path)
    try:
        n = con.execute(
            "SELECT COALESCE(MAX(version_num),0)+1 FROM opt_versions WHERE key=?", (key,)
        ).fetchone()[0]
        cur = con.execute(
            "INSERT INTO opt_versions (key, version_num, value_json, source, rationale, "
            "predicted_delta, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (key, n, value, source, rationale, predicted_delta, status,
             datetime.utcnow().isoformat()),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def get_champion(key, db_path=DB_PATH):
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT id,key,version_num,value_json,source,rationale,predicted_delta,status "
            "FROM opt_versions WHERE key=? AND status='champion' "
            "ORDER BY version_num DESC LIMIT 1", (key,)
        ).fetchone()
        return _row_to_version(r)
    finally:
        con.close()


def promote(version_id, db_path=DB_PATH):
    con = _connect(db_path)
    try:
        row = con.execute("SELECT key FROM opt_versions WHERE id=?", (version_id,)).fetchone()
        if not row:
            return
        key = row[0]
        con.execute(
            "UPDATE opt_versions SET status='retired' WHERE key=? AND status='champion'", (key,)
        )
        con.execute("UPDATE opt_versions SET status='champion' WHERE id=?", (version_id,))
        con.execute(
            "UPDATE opt_assets SET champion_version_id=? WHERE key=?", (version_id, key)
        )
        con.commit()
    finally:
        con.close()


def list_assets(db_path=DB_PATH):
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT key, kind, champion_version_id FROM opt_assets").fetchall()
        return [{"key": r[0], "kind": r[1], "champion_version_id": r[2]} for r in rows]
    finally:
        con.close()
