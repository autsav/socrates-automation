#!/usr/bin/env python
"""Self-improvement loop CLI.

  optimize.py --run              run the loop; surface proposals to Telegram
  optimize.py --dry-run          run the loop; print proposals; notify nothing
  optimize.py --status           print champions + open experiments
  optimize.py --apply-decisions  poll Telegram once; promote/reject per approval
"""
import argparse
import json
import sys
from pathlib import Path

from src.optimizer import loop, registry, experiments, assets
from src.optimizer.proposers import prompt_critic


def _default_surface(proposal, msg):
    """Send the proposal to Telegram with inline approve/reject buttons keyed by
    the challenger version id, and record it pending so --apply-decisions can act.
    Uses optimizer-namespaced (opt-<vid>) callbacks so a tap can never be mistaken
    for a reel post approval."""
    from config import Config
    from src.core.notifier import Notifier
    from src.core import approval
    vid = proposal["challenger_version_id"]
    approval.record_pending_optimizer(vid)
    Notifier(Config()).send_message_with_buttons(msg, approval.optimizer_buttons(vid))


def _default_client():
    from config import Config
    from studio.client import StudioClient
    return StudioClient(Config().ANTHROPIC_API_KEY)


def _perf_context(db_path):
    """Best-effort performance context for the critic (empty at cold start).
    Also appends the sends-per-reach digest so the daily `--run` cycle is
    digest-informed too — without this, `loop.run_once` skipping keys with an
    open experiment meant the weekly digest-fed proposals rarely got a turn
    (IMPORTANT 2)."""
    try:
        p = Path(__file__).parent / "data" / "perf_brief.json"
        base = json.dumps(json.loads(p.read_text())) if p.exists() else "No performance data yet."
    except Exception:
        base = "No performance data yet."
    try:
        from src.analytics.performance_digest import digest_text
        digest = digest_text("story_writer", db_path)
    except Exception:
        digest = ""
    return f"{base}\n{digest}" if digest else base


def main(argv=None, *, client=None, notify=None, db_path=registry.DB_PATH,
         propose_fn=prompt_critic.propose):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--apply-decisions", action="store_true")
    ap.add_argument("--surface-pending", action="store_true",
                    help="Send every open challenger (e.g. hand-seeded) to Telegram for approval.")
    ap.add_argument("--evaluate", action="store_true",
                    help="Score open experiments against real engagement; surface A/B winners.")
    args = ap.parse_args(argv)

    if args.status:
        for a in assets.iter_managed(db_path):
            exp = experiments.get_open_experiment(a["key"], db_path)
            print(f"{a['key']}: champion set; open_experiment={'yes' if exp else 'no'}")
        return 0

    if args.surface_pending:
        from src.core import approval
        count = 0
        for a in assets.iter_managed(db_path):
            exp = experiments.get_open_experiment(a["key"], db_path)
            if not exp:
                continue
            v = registry.get_version(exp["challenger_version_id"], db_path)
            if not v:
                continue
            # Skip ones already awaiting a decision (don't double-send).
            if approval.get_optimizer_decision_status(v["id"]) == "pending":
                continue
            proposal = {
                "key": a["key"], "challenger_version_id": v["id"],
                "rationale": v.get("rationale", ""),
                "predicted_delta": v.get("predicted_delta", 0.0),
                "candidate": v["value"],
            }
            msg = loop.format_proposal_message(proposal)
            print(f"→ surfacing {a['key']} (v#{v['id']})")
            if notify is not None:
                notify(msg)
            else:
                _default_surface(proposal, msg)
            count += 1
        print(f"\nSurfaced {count} pending challenger(s) to Telegram.")
        return 0

    if args.apply_decisions:
        from config import Config
        from src.core import approval
        approval.poll_once(Config())  # refresh the shared decision store
        decisions = approval.get_optimizer_decisions()  # only opt-namespaced, unapplied
        for d in decisions:
            vid = d["version_id"]
            approved = d["status"] == "approved"
            result = loop.apply_decision(vid, approved, db_path)
            approval.mark_optimizer_applied(vid)
            print(f"challenger v#{vid}: {result}")
        print(f"\n{len(decisions)} decision(s).")
        return 0

    if args.evaluate:
        wins = loop.evaluate_experiments(db_path=db_path)
        for p in wins:
            msg = loop.format_proposal_message(p)
            print(msg)
            if notify is not None:
                notify(msg)
            else:
                _default_surface(p, msg)
        print(f"\n{len(wins)} A/B winner(s) surfaced.")
        return 0

    if args.run or args.dry_run:
        if client is None and args.run:
            client = _default_client()
        # Evaluate finished A/B experiments first (data-backed wins → proposals),
        # then ask the critic for new challengers on idle assets.
        proposals = loop.evaluate_experiments(db_path=db_path)
        proposals += loop.run_once(client, _perf_context(db_path), db_path=db_path,
                                   propose_fn=propose_fn)
        for p in proposals:
            msg = loop.format_proposal_message(p)
            print(msg)
            if args.run:
                if notify is not None:
                    notify(msg)              # test seam
                else:
                    _default_surface(p, msg)  # real Telegram w/ approve/reject buttons
        print(f"\n{len(proposals)} proposal(s).")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
