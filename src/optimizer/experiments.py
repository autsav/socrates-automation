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


def evaluate(experiment_id, arm_rewards, min_samples=8, margin=0.05, db_path=registry.DB_PATH):
    champ = arm_rewards.get("champion", [])
    chal = arm_rewards.get("challenger", [])
    cm, hm = _mean(champ), _mean(chal)
    res = {"champion_mean": cm, "challenger_mean": hm,
           "n_champ": len(champ), "n_chal": len(chal)}
    if len(champ) < min_samples or len(chal) < min_samples:
        res["decision"] = "insufficient"
        return res
    res["decision"] = "promote" if hm >= cm * (1 + margin) else "retire"
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
