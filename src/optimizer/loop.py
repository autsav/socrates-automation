"""Nightly self-improvement loop (Phase 1: prompts).

For each managed prompt with no open experiment, ask the critic for a rewrite,
guardrail it, and (if it passes) record a challenger version + open an experiment
+ emit a proposal. Surfacing proposals to Telegram + applying approvals lives in
optimize.py (the CLI). Every asset is handled in isolation; one failure never
aborts the rest."""
import json
import logging
import sqlite3
from src.optimizer import registry, experiments, guardrails, assets, reward
from src.optimizer.proposers import prompt_critic

log = logging.getLogger(__name__)


def evaluate_experiments(db_path=registry.DB_PATH, min_samples=8, margin=0.05):
    """Score every OPEN experiment against real engagement: bucket each post's
    reward into the champion or challenger arm by the version recorded in
    posts.opt_versions_json, then decide. A data-backed WIN becomes a Telegram
    proposal (human still approves the promotion); a LOSS auto-retires the
    challenger; insufficient data leaves the experiment open. Returns the list of
    win-proposals to surface. Never raises."""
    proposals = []
    con = sqlite3.connect(str(db_path))
    try:
        open_exps = con.execute(
            "SELECT id, key, champion_version_id, challenger_version_id "
            "FROM opt_experiments WHERE status='open'").fetchall()
        try:
            rows = con.execute(
                "SELECT p.opt_versions_json, m.likes, m.comments, m.shares, m.reach, m.saved "
                "FROM posts p JOIN post_metrics m ON p.post_id = m.post_id "
                "WHERE p.opt_versions_json IS NOT NULL").fetchall()
        except sqlite3.OperationalError:
            rows = []  # posts/post_metrics not present (e.g. optimizer-only DB)
    finally:
        con.close()

    # Pre-compute reward per (key, version_id) from attributed posts.
    by_key_version = {}
    for opt_json, likes, comments, shares, reach, saved in rows:
        try:
            versions = json.loads(opt_json)
        except (TypeError, ValueError):
            continue
        r = reward.reward({"likes": likes, "comments": comments, "shares": shares,
                           "reach": reach, "saved": saved})
        for key, vid in versions.items():
            by_key_version.setdefault((key, vid), []).append(r)

    for eid, key, champ_id, chal_id in open_exps:
        try:
            arms = {
                "champion": by_key_version.get((key, champ_id), []),
                "challenger": by_key_version.get((key, chal_id), []),
            }
            v = experiments.decide(arms, min_samples=min_samples, margin=margin)
            if v["decision"] == "promote":
                experiments.set_status(eid, "data_win", db_path)
                chal = registry.get_version(chal_id, db_path)
                lift = round((v["challenger_mean"] / max(v["champion_mean"], 1e-9) - 1) * 100)
                proposals.append({
                    "key": key, "challenger_version_id": chal_id,
                    "rationale": (chal.get("rationale", "") +
                                  f" [A/B: +{lift}% over {v['n_chal']} posts]"),
                    "predicted_delta": max(v["challenger_mean"] - v["champion_mean"], 0.0),
                    "candidate": chal["value"],
                })
                log.info(f"[optimizer] {key}: challenger wins A/B (+{lift}%) → proposing")
            elif v["decision"] == "retire":
                experiments.set_status(eid, "retired", db_path)
                registry.retire_version(chal_id, db_path)
                log.info(f"[optimizer] {key}: challenger lost A/B → retired")
        except Exception as e:
            log.warning(f"[optimizer] evaluate failed for {key} ({e})")
            continue
    return proposals


def run_once(client, perf_context, db_path=registry.DB_PATH, propose_fn=prompt_critic.propose,
             expire_days=14):
    # Close out experiments that have been open too long (ignored proposals) so
    # their assets are eligible for a fresh proposal this cycle (critique B2).
    try:
        stale = experiments.expire_stale(max_age_days=expire_days, db_path=db_path)
        if stale:
            log.info(f"[optimizer] expired {len(stale)} stale experiment(s)")
    except Exception as e:
        log.warning(f"[optimizer] expire_stale failed ({e})")
    proposals = []
    for m in assets.iter_managed(db_path):
        key, champ = m["key"], m["champion_text"]
        try:
            if experiments.get_open_experiment(key, db_path):
                continue
            cand = propose_fn(client, key, champ, perf_context)
            if not cand:
                continue
            if float(cand.get("predicted_delta", 0) or 0) <= 0:
                continue
            ok, reason = guardrails.validate_prompt_candidate(champ, cand["candidate"])
            if not ok:
                log.info(f"[optimizer] {key}: candidate rejected ({reason})")
                continue
            champ_v = registry.get_champion(key, db_path)
            cid = registry.add_version(
                key, cand["candidate"], source="critic",
                rationale=cand.get("rationale", ""),
                predicted_delta=cand["predicted_delta"], status="challenger", db_path=db_path,
            )
            experiments.open_experiment(key, champ_v["id"], cid, db_path=db_path)
            proposals.append({
                "key": key, "challenger_version_id": cid,
                "rationale": cand.get("rationale", ""),
                "predicted_delta": cand["predicted_delta"],
                "candidate": cand["candidate"],
            })
        except Exception as e:
            log.warning(f"[optimizer] loop failed for {key} ({e})")
            continue
    return proposals


def format_proposal_message(proposal):
    pct = round(float(proposal.get("predicted_delta", 0)) * 100)
    cand = proposal.get("candidate", "")
    if len(cand) > 800:
        cand = cand[:800] + "…"
    return (
        f"🧠 Prompt improvement proposed\n"
        f"Asset: {proposal['key']}\n"
        f"Predicted: +{pct}% engagement\n"
        f"Why: {proposal.get('rationale','')}\n\n"
        f"New prompt:\n{cand}\n\n"
        f"Challenger v#{proposal.get('challenger_version_id')} — approve to make champion."
    )


def apply_decision(challenger_version_id, approved, db_path=registry.DB_PATH):
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT key FROM opt_versions WHERE id=?",
                          (challenger_version_id,)).fetchone()
        if not row:
            return "noop"
        exp = con.execute(
            "SELECT id FROM opt_experiments WHERE challenger_version_id=? "
            "AND status IN ('open','data_win')",
            (challenger_version_id,)).fetchone()
    finally:
        con.close()

    if approved:
        registry.promote(challenger_version_id, db_path)
        if exp:
            con = sqlite3.connect(str(db_path))
            try:
                con.execute("UPDATE opt_experiments SET status='promoted' WHERE id=?", (exp[0],))
                con.commit()
            finally:
                con.close()
        return "promoted"

    con = sqlite3.connect(str(db_path))
    try:
        con.execute("UPDATE opt_versions SET status='rejected' WHERE id=?",
                   (challenger_version_id,))
        if exp:
            con.execute("UPDATE opt_experiments SET status='retired' WHERE id=?", (exp[0],))
        con.commit()
    finally:
        con.close()
    return "rejected"
