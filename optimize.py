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


def _default_notify(msg):
    from config import Config
    from src.core.notifier import Notifier
    Notifier(Config()).send(msg)


def _default_client():
    from config import Config
    from studio.client import StudioClient
    return StudioClient(Config().ANTHROPIC_API_KEY)


def _perf_context(db_path):
    """Best-effort performance context for the critic (empty at cold start)."""
    try:
        p = Path(__file__).parent / "data" / "perf_brief.json"
        return json.dumps(json.loads(p.read_text())) if p.exists() else "No performance data yet."
    except Exception:
        return "No performance data yet."


def main(argv=None, *, client=None, notify=None, db_path=registry.DB_PATH,
         propose_fn=prompt_critic.propose):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--apply-decisions", action="store_true")
    args = ap.parse_args(argv)

    if args.status:
        for a in assets.iter_managed(db_path):
            exp = experiments.get_open_experiment(a["key"], db_path)
            print(f"{a['key']}: champion set; open_experiment={'yes' if exp else 'no'}")
        return 0

    if args.apply_decisions:
        from config import Config
        from src.core import approval
        decisions = approval.poll_once(Config())
        for d in decisions:
            vid = d.get("post_row_id")
            approved = d.get("status") == "approved"
            result = loop.apply_decision(vid, approved, db_path)
            print(f"challenger v#{vid}: {result}")
        print(f"\n{len(decisions)} decision(s).")
        return 0

    if args.run or args.dry_run:
        if client is None and args.run:
            client = _default_client()
        proposals = loop.run_once(client, _perf_context(db_path), db_path=db_path,
                                  propose_fn=propose_fn)
        for p in proposals:
            msg = loop.format_proposal_message(p)
            print(msg)
            if args.run:
                (notify or _default_notify)(msg)
        print(f"\n{len(proposals)} proposal(s).")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
