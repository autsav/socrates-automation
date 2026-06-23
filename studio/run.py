"""Studio orchestrator — chains the four agents; returns None to signal fallback."""
import logging

from studio import analyst, strategist, copywriter, director
from studio.client import StudioClient, StudioError

log = logging.getLogger(__name__)


def run_studio(client, slot, pool, recent_posts):
    """Run the full creative chain for one slot.

    Returns (CreativeBrief, Decision, concepts_by_id) on success, or None if the
    daily spend ceiling is hit or any agent fails — the signal for pipeline.py to
    fall back to the legacy templated path.
    """
    if client.over_daily_ceiling():
        log.warning("[studio] daily spend ceiling reached — falling back to legacy")
        return None
    try:
        perf = analyst.get_or_build_brief(client)
        brief = strategist.make_brief(client, perf, slot, recent_posts, pool)
        concepts = copywriter.draft(client, perf, brief)
        decision = director.review(client, perf, brief, concepts)
        cmap = {c.id: c for c in concepts}
        return brief, decision, cmap
    except StudioError as e:
        log.warning("[studio] agent failure (%s) — falling back to legacy", e)
        return None


def _build_pool(excel_path):
    """Read all ready (unposted, non-skip) quote rows from quotes.xlsx."""
    import openpyxl
    wb = openpyxl.load_workbook(excel_path)
    ws = wb["Quotes"]
    rows = []
    for row in ws.iter_rows(min_row=2, values_only=False):
        quote, caption = row[1].value, row[3].value
        status, posted = row[6].value, row[7].value
        if quote and caption and not posted and str(status).lower() != "skip":
            rows.append({
                "row_number": row[0].value,
                "quote": str(quote).strip(),
                "audience": str(row[2].value).strip().lower() if row[2].value else "stuck",
            })
    return rows


if __name__ == "__main__":
    import argparse
    import json
    from config import Config
    from excel_reader import _current_slot
    import data_store

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the chain and print the proposal; do not post.")
    args = parser.parse_args()

    cfg = Config()
    data_store.init_db()
    client = StudioClient(cfg.ANTHROPIC_API_KEY)
    pool = _build_pool("quotes.xlsx")
    out = run_studio(client, _current_slot(), pool, [])
    if out is None:
        print("Studio fell back (legacy path would run).")
    else:
        brief, decision, _ = out
        print(json.dumps({"brief": brief.to_dict(),
                          "decision": decision.to_dict()}, indent=2))
