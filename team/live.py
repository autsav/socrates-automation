"""Run the team pipeline with a live HTML dashboard.

Usage: python -m team.live [--dry-run]
Opens http://localhost:5001 — open in a browser to watch every agent work,
debate, and produce content live.
"""
from __future__ import annotations

from src.utils.logger import get_logger
logger = get_logger(__name__)

import argparse
import threading
import webbrowser

from team.dashboard import PORT, app, bus, make_callbacks
from team.orchestrator import run_team_pipeline


def _run_pipeline(dry_run: bool) -> None:
    try:
        result = run_team_pipeline(dry_run=dry_run, **make_callbacks(bus))
    except Exception as exc:
        bus.publish({"type": "pipeline_failed", "error": str(exc)})
        return
    paths = ", ".join(str(p) for p in result["output_paths"].values())
    bus.publish({
        "type": "pipeline_complete",
        "summary": f"wrote {len(result['output_paths'])} artifacts: {paths}",
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the full team chain and save outputs; do not post.")
    args = parser.parse_args()

    threading.Thread(target=_run_pipeline, args=(args.dry_run,), daemon=True).start()

    url = f"http://localhost:{PORT}"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    logger.info(f"Live dashboard: {url}")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
