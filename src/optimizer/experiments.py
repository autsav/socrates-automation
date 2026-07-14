"""Champion-challenger experiments. evaluate() is pure w.r.t. the reward lists
passed in — the caller collects per-arm rewards from post_metrics (Phase 1
tests pass them directly; the pipeline wires real attribution later)."""
import json
import sqlite3
from datetime import datetime
from src.optimizer import registry


def _connect(db_path):
    return sqlite3.connect(str(db_path))


def open_experiment(key, champion_version_id, challenger_version_id, metric="reward",
                    db_path=registry.DB_PATH):
    con = _connect(db_path)
    try:
        cur = con.execute(
            "INSERT INTO opt_experiments (key, champion_version_id, challenger_version_id, "
            "metric, status, opened_at) VALUES (?,?,?,?, 'open', ?)",
            (key, champion_version_id, challenger_version_id, metric,
             datetime.utcnow().isoformat()),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def expire_stale(max_age_days=14, db_path=registry.DB_PATH, now=None):
    """Close open experiments older than `max_age_days` (status='expired') and
    retire their challenger, so an ignored proposal can't stall its asset forever
    (critique B2). Returns the list of expired experiment ids. `now` is injectable
    for tests (defaults to utcnow)."""
    now = now or datetime.utcnow()
    con = _connect(db_path)
    expired = []
    try:
        rows = con.execute(
            "SELECT id, opened_at, challenger_version_id FROM opt_experiments "
            "WHERE status='open'"
        ).fetchall()
        for eid, opened_at, chal_id in rows:
            try:
                opened = datetime.fromisoformat(opened_at)
            except (TypeError, ValueError):
                continue
            if (now - opened).total_seconds() >= max_age_days * 86400:
                con.execute("UPDATE opt_experiments SET status='expired', closed_at=? "
                            "WHERE id=?", (now.isoformat(), eid))
                con.execute("UPDATE opt_versions SET status='retired' WHERE id=? "
                            "AND status='challenger'", (chal_id,))
                expired.append(eid)
        con.commit()
    finally:
        con.close()
    return expired


def set_status(experiment_id, status, db_path=registry.DB_PATH):
    """Set an experiment's status. Stamps closed_at for terminal states."""
    con = _connect(db_path)
    try:
        closed = datetime.utcnow().isoformat() if status in ("retired", "promoted", "expired") else None
        con.execute("UPDATE opt_experiments SET status=?, closed_at=? WHERE id=?",
                    (status, closed, experiment_id))
        con.commit()
    finally:
        con.close()


def get_open_experiment(key, db_path=registry.DB_PATH):
    con = _connect(db_path)
    try:
        r = con.execute(
            "SELECT id, key, champion_version_id, challenger_version_id, metric "
            "FROM opt_experiments WHERE key=? AND status='open' "
            "ORDER BY id DESC LIMIT 1", (key,)
        ).fetchone()
        if not r:
            return None
        return {"id": r[0], "key": r[1], "champion_version_id": r[2],
                "challenger_version_id": r[3], "metric": r[4]}
    finally:
        con.close()


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def decide(arm_rewards, min_samples=8, margin=0.05):
    """Pure verdict from per-arm reward lists — no DB mutation. Returns
    {decision: promote|retire|insufficient, champion_mean, challenger_mean, n_champ, n_chal}."""
    champ = arm_rewards.get("champion", [])
    chal = arm_rewards.get("challenger", [])
    cm, hm = _mean(champ), _mean(chal)
    res = {"champion_mean": cm, "challenger_mean": hm,
           "n_champ": len(champ), "n_chal": len(chal)}
    if len(champ) < min_samples or len(chal) < min_samples:
        res["decision"] = "insufficient"
    else:
        res["decision"] = "promote" if hm >= cm * (1 + margin) else "retire"
    return res


def evaluate(experiment_id, arm_rewards, min_samples=8, margin=0.05, db_path=registry.DB_PATH):
    res = decide(arm_rewards, min_samples, margin)
    if res["decision"] == "insufficient":
        return res
    con = _connect(db_path)
    try:
        status = "promoted" if res["decision"] == "promote" else "retired"
        con.execute(
            "UPDATE opt_experiments SET status=?, closed_at=?, result_json=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), json.dumps(res), experiment_id),
        )
        con.commit()
    finally:
        con.close()
    return res
