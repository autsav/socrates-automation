"""Optimizable asset registry — versioned prompts/policies/weights in SQLite.

Each asset has a champion version (active) + history. Additive migrations only,
matching src/core/data_store.py conventions. Never raises on read paths.

Stale-champion guard: `opt_assets.default_hash` records the hash of the code
default last seeded for a key. When a caller's code default changes (e.g. a
playbook rewrite), `register_asset` detects the hash mismatch and re-seeds the
new default as champion — inserting a fresh version, retiring the old one —
so an edited default is never permanently shadowed by a stale DB row (see
`_reseed_on_default_change`)."""
import hashlib
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
            CREATE TABLE IF NOT EXISTS ab_results (
                dimension TEXT NOT NULL,
                variant_a TEXT NOT NULL,
                variant_b TEXT NOT NULL,
                wins_a INTEGER DEFAULT 0,
                wins_b INTEGER DEFAULT 0,
                trials INTEGER DEFAULT 0,
                last_updated TEXT,
                PRIMARY KEY (dimension, variant_a, variant_b)
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


_INITIALIZED = set()  # db_path strings that have been init_optimizer_db'd


def _ensure_initialized(db_path):
    """Run init_optimizer_db once per db_path, then skip (idempotent)."""
    key = str(db_path)
    if key not in _INITIALIZED:
        init_optimizer_db(db_path)
        _INITIALIZED.add(key)


def _hash_value(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _ensure_default_hash_column(con):
    """Additive migration: add opt_assets.default_hash if missing, backfilled from
    each key's seed v1 version so unchanged defaults don't spuriously re-seed."""
    cols = [r[1] for r in con.execute("PRAGMA table_info(opt_assets)").fetchall()]
    if "default_hash" in cols:
        return
    con.execute("ALTER TABLE opt_assets ADD COLUMN default_hash TEXT")
    for (key,) in con.execute("SELECT key FROM opt_assets").fetchall():
        v1 = con.execute(
            "SELECT value_json FROM opt_versions WHERE key=? AND version_num=1 "
            "ORDER BY id LIMIT 1", (key,)
        ).fetchone()
        if v1:
            con.execute(
                "UPDATE opt_assets SET default_hash=? WHERE key=?",
                (_hash_value(v1[0]), key),
            )
    con.commit()


def register_asset(key, kind, seed_value, db_path=DB_PATH):
    _ensure_initialized(db_path)
    con = _connect(db_path)
    try:
        _ensure_default_hash_column(con)
        new_hash = _hash_value(seed_value)
        existing = con.execute(
            "SELECT champion_version_id, default_hash FROM opt_assets WHERE key=?", (key,)
        ).fetchone()
        now = datetime.utcnow().isoformat()
        if not existing or existing[0] is None:
            cur = con.execute(
                "INSERT INTO opt_versions (key, version_num, value_json, source, rationale, "
                "predicted_delta, status, created_at) VALUES (?,1,?,?,?,0.0,'champion',?)",
                (key, seed_value, "seed", "seed v1", now),
            )
            vid = cur.lastrowid
            con.execute(
                "INSERT OR REPLACE INTO opt_assets (key, kind, champion_version_id, "
                "created_at, default_hash) VALUES (?,?,?,?,?)",
                (key, kind, vid, now, new_hash),
            )
            con.commit()
            return vid

        champion_id, stored_hash = existing
        if stored_hash != new_hash:
            return _reseed_on_default_change(con, key, seed_value, new_hash, now)
        return champion_id
    finally:
        con.close()


def _reseed_on_default_change(con, key, seed_value, new_hash, now):
    """The code default for `key` no longer matches the hash recorded at last
    seed/reseed — insert the new default as a fresh champion version (history
    preserved) and retire whatever was champion before it."""
    n = con.execute(
        "SELECT COALESCE(MAX(version_num),0)+1 FROM opt_versions WHERE key=?", (key,)
    ).fetchone()[0]
    cur = con.execute(
        "INSERT INTO opt_versions (key, version_num, value_json, source, rationale, "
        "predicted_delta, status, created_at) VALUES (?,?,?,?,?,0.0,'champion',?)",
        (key, n, seed_value, "default-reseed", "code default changed", now),
    )
    new_vid = cur.lastrowid
    con.execute(
        "UPDATE opt_versions SET status='retired' WHERE key=? AND status='champion' AND id!=?",
        (key, new_vid),
    )
    con.execute(
        "UPDATE opt_assets SET champion_version_id=?, default_hash=? WHERE key=?",
        (new_vid, new_hash, key),
    )
    con.commit()
    return new_vid


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


def retire_version(version_id, db_path=DB_PATH):
    con = _connect(db_path)
    try:
        con.execute("UPDATE opt_versions SET status='retired' WHERE id=?", (version_id,))
        con.commit()
    finally:
        con.close()


def get_version(version_id, db_path=DB_PATH):
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT id,key,version_num,value_json,source,rationale,predicted_delta,status "
            "FROM opt_versions WHERE id=?", (version_id,)
        ).fetchone()
        return _row_to_version(r)
    finally:
        con.close()


def list_assets(db_path=DB_PATH):
    con = _connect(db_path)
    try:
        rows = con.execute("SELECT key, kind, champion_version_id FROM opt_assets").fetchall()
        return [{"key": r[0], "kind": r[1], "champion_version_id": r[2]} for r in rows]
    finally:
        con.close()
