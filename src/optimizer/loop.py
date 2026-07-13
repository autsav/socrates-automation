"""Nightly self-improvement loop (Phase 1: prompts).

For each managed prompt with no open experiment, ask the critic for a rewrite,
guardrail it, and (if it passes) record a challenger version + open an experiment
+ emit a proposal. Surfacing proposals to Telegram + applying approvals lives in
optimize.py (the CLI). Every asset is handled in isolation; one failure never
aborts the rest."""
import logging
import sqlite3
from src.optimizer import registry, experiments, guardrails, assets
from src.optimizer.proposers import prompt_critic

log = logging.getLogger(__name__)


def run_once(client, perf_context, db_path=registry.DB_PATH, propose_fn=prompt_critic.propose):
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
            "SELECT id FROM opt_experiments WHERE challenger_version_id=? AND status='open'",
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
