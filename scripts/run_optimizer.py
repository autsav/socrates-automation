"""Weekly optimizer entrypoint (spec 2.4): evaluate running experiments, then
let prompt_critic propose challengers with REAL performance context.

`evaluate_experiments` scores open A/B experiments against real engagement and
returns any data-backed win-proposals (still requires human approval to
promote). `run_once` then asks the critic for fresh challengers per managed
prompt, guardrails them, and — on success — records a challenger version and
opens a new experiment (queued via the opt_versions/opt_experiments tables).
Both proposal lists are printed via loop.format_proposal_message AND surfaced
to Telegram (approve/reject buttons) via optimize.py's `_default_surface` —
the same mechanism `optimize.py --run`/`--surface-pending` use. Surfacing is
best-effort: a Telegram failure never fails the weekly workflow, and
`--dry-run` prints proposals without surfacing them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import loop


def _digest():
    from src.analytics.performance_digest import digest_text
    return digest_text("story_writer")


def _client():
    from config import Config
    from studio.client import StudioClient
    return StudioClient(Config().ANTHROPIC_API_KEY)


def _surface(proposal, msg):
    """Surface a proposal to Telegram via optimize.py's existing notifier plumbing
    (same mechanism as `optimize.py --run` / `--surface-pending`). Best-effort: a
    Telegram failure must never fail the weekly workflow."""
    try:
        import optimize
        optimize._default_surface(proposal, msg)
    except Exception as e:  # noqa: BLE001 - best-effort, never block the weekly run
        print(f"[optimizer] surface failed: {e}")


def _print_proposal(p, *, surface=True):
    try:
        msg = loop.format_proposal_message(p)
    except Exception as e:  # noqa: BLE001 - malformed proposal never aborts the run
        print(f"[optimizer] could not format proposal: {e}")
        return
    print(msg)
    if surface:
        _surface(p, msg)


def main(dry_run=False) -> int:
    try:
        evaluated = loop.evaluate_experiments()
    except Exception as e:  # noqa: BLE001 - best-effort, never block the weekly run
        print(f"[optimizer] evaluate_experiments failed: {e}")
        evaluated = []
    print(f"[optimizer] experiments evaluated: {len(evaluated)} win-proposal(s)")
    for p in evaluated:
        _print_proposal(p, surface=not dry_run)

    proposals = loop.run_once(_client(), _digest()) or []
    for p in proposals:
        _print_proposal(p, surface=not dry_run)
    if dry_run:
        print(f"[optimizer] dry-run: {len(proposals)} proposal(s), not queued")
    return len(proposals)


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
