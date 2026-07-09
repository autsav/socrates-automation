"""Team orchestrator — wires every team agent into one sequential pipeline.

Order: analytics -> (planner <-> reviewer debate) -> content writer -> visual
designer -> audio engineer -> video editor -> engagement strategist. Every
artifact is written to team/output/ as indent=2 JSON, keyed by the approved
plan's date. Sequential by design (low-frequency batch job, not a hot path) —
do not add concurrency here.

`dry_run` is accepted and threaded through for a future task to wire real
posting via pipeline.py; this module deliberately never imports pipeline.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from studio.client import StudioClient
from studio.run import _build_pool
from src.core import data_store

from team.analytics_analyst import AnalyticsAnalystAgent
from team.planner import PlannerAgent
from team.reviewer import ReviewerAgent
from team.debate import run_debate
from team.content_writer import ContentWriterAgent
from team.visual_designer import VisualDesignerAgent
from team.audio_engineer import AudioEngineerAgent
from team.video_editor import VideoEditorAgent
from team.engagement_strategist import EngagementStrategistAgent

_OUTPUT_DIR = Path(__file__).parent / "output"


def run_team_pipeline(dry_run: bool = True, *, client=None, now: datetime | None = None) -> dict:
    if client is None:
        from config import Config
        cfg = Config()
        client = StudioClient(cfg.ANTHROPIC_API_KEY)

    data_store.init_db()

    analytics_report = AnalyticsAnalystAgent(client).run(now=now)
    quotes_pool = _build_pool("quotes.xlsx")

    approved_plan, debate_history = run_debate(
        PlannerAgent(client), ReviewerAgent(client), analytics_report, quotes_pool, now=now
    )

    copy_specs = ContentWriterAgent(client).run(approved_plan)
    visual_specs = VisualDesignerAgent(client).run(approved_plan, copy_specs)
    audio_specs = AudioEngineerAgent(client).run(approved_plan, copy_specs)
    video_specs = VideoEditorAgent(client).run(approved_plan, visual_specs, audio_specs)
    engagement_specs = EngagementStrategistAgent(client).run(approved_plan, copy_specs)

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = approved_plan.date

    artifacts = {
        "approved_plan": approved_plan.to_dict(),
        "analytics_report": analytics_report.to_dict(),
        "copy": {"items": [c.to_dict() for c in copy_specs]},
        "visual_specs": {"items": [v.to_dict() for v in visual_specs]},
        "audio_specs": {"items": [a.to_dict() for a in audio_specs]},
        "video_specs": {"items": [v.to_dict() for v in video_specs]},
        "engagement_specs": {"items": [e.to_dict() for e in engagement_specs]},
    }

    output_paths = {}
    for key, payload in artifacts.items():
        path = _OUTPUT_DIR / f"{key}_{date}.json"
        path.write_text(json.dumps(payload, indent=2))
        output_paths[key] = path

    return {
        "analytics_report": analytics_report,
        "approved_plan": approved_plan,
        "debate_history": debate_history,
        "copy_specs": copy_specs,
        "visual_specs": visual_specs,
        "audio_specs": audio_specs,
        "video_specs": video_specs,
        "engagement_specs": engagement_specs,
        "output_paths": output_paths,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the full team chain and save outputs; do not post.")
    args = parser.parse_args()
    result = run_team_pipeline(dry_run=args.dry_run)
    print(json.dumps({"output_paths": {k: str(v) for k, v in
                      result["output_paths"].items()}}, indent=2))
