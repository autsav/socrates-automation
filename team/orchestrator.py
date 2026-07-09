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
from datetime import date as date_cls, datetime
from pathlib import Path
from typing import Callable

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


class PlanNotApprovedError(RuntimeError):
    """Raised when the reviewer never approves the plan within max_rounds —
    stops the pipeline before any downstream (paid) agents run on it."""


def _current_spend_usd() -> float:
    """Today's cumulative spend from studio's daily spend log (best-effort)."""
    from studio import settings as studio_settings
    try:
        log = json.loads(studio_settings.SPEND_LOG_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return 0.0
    return log.get(date_cls.today().isoformat(), 0.0)


def _stage(
    name: str,
    fn: Callable[[], object],
    summarize: Callable[[object], str],
    *,
    on_stage_start: Callable[[str], None] | None,
    on_stage_done: Callable[[str, str], None] | None,
    on_stage_failed: Callable[[str, str], None] | None,
    on_cost_update: Callable[[float], None] | None,
) -> object:
    if on_stage_start is not None:
        on_stage_start(name)
    try:
        result = fn()
    except Exception as exc:
        if on_stage_failed is not None:
            on_stage_failed(name, str(exc))
        raise
    if on_cost_update is not None:
        on_cost_update(_current_spend_usd())
    if on_stage_done is not None:
        on_stage_done(name, summarize(result))
    return result


def run_team_pipeline(
    dry_run: bool = True,
    *,
    client=None,
    now: datetime | None = None,
    on_stage_start: Callable[[str], None] | None = None,
    on_stage_done: Callable[[str, str], None] | None = None,
    on_stage_failed: Callable[[str, str], None] | None = None,
    on_agent_activity: Callable[[str, str], None] | None = None,
    on_debate_round: Callable[[int, str, str, float, bool], None] | None = None,
    on_log: Callable[[str, str], None] | None = None,
    on_cost_update: Callable[[float], None] | None = None,
    on_deliverable: Callable[[str, str], None] | None = None,
) -> dict:
    if client is None:
        from config import Config
        cfg = Config()
        client = StudioClient(cfg.ANTHROPIC_API_KEY)

    if on_log is not None:
        on_log("info", "Pipeline starting")

    data_store.init_db()

    def stage(name, fn, summarize):
        return _stage(
            name, fn, summarize,
            on_stage_start=on_stage_start, on_stage_done=on_stage_done,
            on_stage_failed=on_stage_failed, on_cost_update=on_cost_update,
        )

    if on_agent_activity is not None:
        on_agent_activity("Analytics Analyst", "Analyzing recent post performance...")
    analytics_report = stage(
        "analytics",
        lambda: AnalyticsAnalystAgent(client).run(now=now),
        lambda r: f"{r.total_posts} posts analyzed, avg engagement {r.avg_engagement_rate:.1%}",
    )
    if on_deliverable is not None:
        on_deliverable("Analytics Analyst", f"Top hooks: {', '.join(analytics_report.top_performing_hooks)}")

    quotes_pool = _build_pool("quotes.xlsx")

    if on_agent_activity is not None:
        on_agent_activity("Planner", "Drafting content plan and debating with Reviewer...")

    def _on_round(round_number, planner_output, reviewer_output, score, approved):
        if on_agent_activity is not None:
            verdict = "APPROVED" if approved else "REVISE"
            on_agent_activity("Reviewer", f"Round {round_number} score {score:.1f}/10 — {verdict}")
        if on_debate_round is not None:
            on_debate_round(round_number, planner_output, reviewer_output, score, approved)

    def _run_debate_or_raise():
        plan, history = run_debate(
            PlannerAgent(client), ReviewerAgent(client), analytics_report, quotes_pool,
            now=now, on_round=_on_round,
        )
        if not history[-1].approved:
            raise PlanNotApprovedError(
                f"reviewer never approved the plan after {len(history)} round(s) "
                f"(final score {history[-1].reviewer_score:.1f}/10) — aborting "
                "before any downstream agents run"
            )
        return plan, history

    approved_plan, debate_history = stage(
        "debate",
        _run_debate_or_raise,
        lambda result: f"Plan approved after {len(result[1])} round(s), "
                       f"score {result[1][-1].reviewer_score:.1f}/10",
    )
    if on_deliverable is not None:
        on_deliverable("Planner", f"7-day plan approved for {approved_plan.date}")

    if on_agent_activity is not None:
        on_agent_activity("Content Writer", "Writing hooks, captions, and CTAs...")
    copy_specs = stage(
        "content_writer",
        lambda: ContentWriterAgent(client).run(approved_plan),
        lambda specs: f"Copy written for {len(specs)} posts",
    )
    if on_deliverable is not None:
        on_deliverable("Content Writer", f"Hooks, captions, CTAs for {len(copy_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Visual Designer", "Designing FLUX prompts and color palettes...")
    visual_specs = stage(
        "visual_designer",
        lambda: VisualDesignerAgent(client).run(approved_plan, copy_specs),
        lambda specs: f"Visual specs designed for {len(specs)} posts",
    )
    if on_deliverable is not None:
        on_deliverable("Visual Designer", f"FLUX prompts, color palettes for {len(visual_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Audio Engineer", "Selecting music tracks and voiceover scripts...")
    audio_specs = stage(
        "audio_engineer",
        lambda: AudioEngineerAgent(client).run(approved_plan, copy_specs),
        lambda specs: f"Audio specs designed for {len(specs)} posts",
    )
    if on_deliverable is not None:
        on_deliverable("Audio Engineer", f"Music tracks, voiceover scripts for {len(audio_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Video Editor", "Sequencing scenes and transitions...")
    video_specs = stage(
        "video_editor",
        lambda: VideoEditorAgent(client).run(approved_plan, visual_specs, audio_specs),
        lambda specs: f"Video specs designed for {len(specs)} posts",
    )
    if on_deliverable is not None:
        on_deliverable("Video Editor", f"Scene sequences, transitions for {len(video_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Engagement Strategist", "Writing seed comments and DM triggers...")
    engagement_specs = stage(
        "engagement_strategist",
        lambda: EngagementStrategistAgent(client).run(approved_plan, copy_specs),
        lambda specs: f"Engagement specs designed for {len(specs)} posts",
    )
    if on_deliverable is not None:
        on_deliverable("Engagement Strategist", f"Seed comments, DM triggers for {len(engagement_specs)} posts")

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

    if on_log is not None:
        on_log("info", "Pipeline complete")

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
