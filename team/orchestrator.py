"""Team orchestrator — wires every team agent into one sequential pipeline.

Order: analytics -> trend scraper -> (planner <-> reviewer debate) -> content
writer -> visual designer -> audio engineer -> video editor -> video quality
reviewer -> engagement strategist. Every artifact is written to team/output/
as indent=2 JSON, keyed by the approved plan's date. Sequential by design
(low-frequency batch job, not a hot path) — do not add concurrency here.

`dry_run` is accepted and threaded through for a future task to wire real
posting via pipeline.py; this module deliberately never imports pipeline.

Checkpoint/resume: after each stage completes, its serialized result is
written to team/output/checkpoint_{run_date}.json. Passing resume_from=<stage
name> loads that checkpoint and skips every stage before it (reconstructing
their typed results from disk) instead of re-running them — so a run that
died at, say, "video_editor" can resume from there without re-paying for
analytics/trend_scraper/debate/content_writer/visual_designer/audio_engineer.
"""
from __future__ import annotations

from src.utils.logger import get_logger
logger = get_logger(__name__)

import json
from datetime import date as date_cls, datetime
from pathlib import Path
from typing import Callable

from studio.client import StudioClient
from studio.run import _build_pool
from src.core import data_store

from team.analytics_analyst import AnalyticsAnalystAgent
from team.trend_scraper import TrendScraperAgent
from team.planner import PlannerAgent
from team.reviewer import ReviewerAgent, VideoQualityReviewerAgent
from team.debate import run_debate
from team.content_writer import ContentWriterAgent
from team.visual_designer import VisualDesignerAgent
from team.audio_engineer import AudioEngineerAgent
from team.video_editor import VideoEditorAgent
from team.engagement_strategist import EngagementStrategistAgent
from team.models import (
    AnalyticsReport, ContentPlan, DebateResult, TrendReport,
    CopySpec, VisualSpec, AudioSpec, VideoSpec, VideoQualityScore, EngagementSpec,
)

_OUTPUT_DIR = Path(__file__).parent / "output"

# Stage execution order — resume_from must be one of these names.
_STAGE_ORDER = [
    "analytics", "trend_scraper", "debate", "content_writer", "visual_designer",
    "audio_engineer", "video_editor", "video_quality_reviewer", "engagement_strategist",
]


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


def _checkpoint_path(run_date: str) -> Path:
    return _OUTPUT_DIR / f"checkpoint_{run_date}.json"


def _save_checkpoint(run_date: str, stage_name: str, payload: dict) -> None:
    """Merge this stage's serialized result into the run's checkpoint file.
    Best-effort: a checkpoint write failure must never fail the pipeline."""
    try:
        path = _checkpoint_path(run_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text())
            except (OSError, ValueError):
                existing = {}
        results = existing.get("results", {})
        results[stage_name] = payload
        existing["results"] = results
        existing["last_checkpoint"] = stage_name
        path.write_text(json.dumps(existing, indent=2))
    except OSError:
        pass


def _load_checkpoint(run_date: str) -> dict | None:
    path = _checkpoint_path(run_date)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


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
    dry_run: bool = False,
    *,
    client=None,
    now: datetime | None = None,
    resume_from: str | None = None,
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

    if resume_from is not None and resume_from not in _STAGE_ORDER:
        raise ValueError(f"resume_from must be one of {_STAGE_ORDER}, got {resume_from!r}")

    if on_log is not None:
        on_log("info", "Pipeline starting" if resume_from is None
                else f"Pipeline resuming from {resume_from!r}")

    if dry_run:
        # Wrap the studio client's paid call so dry-run never spends tokens.
        # Only mutate when a client is present (caller-passed or just built);
        # instance-method assignment is safe for real StudioClient and mocks.
        if client is not None:
            def _dry_call(*a, **kw):
                logger.info("DRY-RUN: skipping paid studio call %s",
                            a[0] if a else "unknown")
                return {}
            client.call = _dry_call
        if on_log is not None:
            on_log("info", "DRY-RUN: paid studio calls wrapped to no-ops")

    data_store.init_db()

    run_date = (now or datetime.utcnow()).date().isoformat()
    checkpoint = _load_checkpoint(run_date) if resume_from is not None else None
    resume_index = _STAGE_ORDER.index(resume_from) if resume_from is not None else 0

    def stage(name, fn, summarize):
        return _stage(
            name, fn, summarize,
            on_stage_start=on_stage_start, on_stage_done=on_stage_done,
            on_stage_failed=on_stage_failed, on_cost_update=on_cost_update,
        )

    def checkpointed(name, fn, summarize, serialize, deserialize):
        """Run `stage(name, fn, summarize)` and persist its serialized result,
        unless this stage precedes resume_from and a checkpointed result for
        it already exists on disk — in which case that result is loaded
        instead of re-running (and re-paying for) the stage."""
        idx = _STAGE_ORDER.index(name)
        if idx < resume_index and checkpoint and name in checkpoint.get("results", {}):
            result = deserialize(checkpoint["results"][name])
            if on_stage_start is not None:
                on_stage_start(name)
            if on_stage_done is not None:
                on_stage_done(name, f"resumed from checkpoint ({summarize(result)})")
            return result
        result = stage(name, fn, summarize)
        if not dry_run:
            _save_checkpoint(run_date, name, serialize(result))
        return result

    if on_agent_activity is not None:
        on_agent_activity("Analytics Analyst", "Analyzing recent post performance...")
    analytics_report = checkpointed(
        "analytics",
        lambda: AnalyticsAnalystAgent(client).run(now=now),
        lambda r: f"{r.total_posts} posts analyzed, avg engagement {r.avg_engagement_rate:.1%}",
        lambda r: r.to_dict(),
        AnalyticsReport.from_dict,
    )
    if on_deliverable is not None:
        on_deliverable("Analytics Analyst", f"Top hooks: {', '.join(analytics_report.top_performing_hooks)}")

    if on_agent_activity is not None:
        on_agent_activity("Trend Scraper", "Fetching trending hashtags and sounds from TikTok...")
    trend_report = checkpointed(
        "trend_scraper",
        lambda: TrendScraperAgent().run(),
        lambda r: f"{len(r.hashtags)} trending hashtags, {len(r.sounds)} trending sounds fetched",
        lambda r: r.to_dict(),
        TrendReport.from_dict,
    )
    if on_deliverable is not None:
        on_deliverable("Trend Scraper", f"{len(trend_report.hashtags)} hashtags, "
                                        f"{len(trend_report.sounds)} sounds trending")

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

    approved_plan, debate_history = checkpointed(
        "debate",
        _run_debate_or_raise,
        lambda result: f"Plan approved after {len(result[1])} round(s), "
                       f"score {result[1][-1].reviewer_score:.1f}/10",
        lambda result: {"plan": result[0].to_dict(),
                        "history": [h.to_dict() for h in result[1]]},
        lambda d: (ContentPlan.from_dict(d["plan"]),
                  [DebateResult.from_dict(h) for h in d["history"]]),
    )
    if on_deliverable is not None:
        on_deliverable("Planner", f"7-day plan approved for {approved_plan.date}")

    if on_agent_activity is not None:
        on_agent_activity("Content Writer", "Writing hooks, captions, and CTAs...")
    copy_specs = checkpointed(
        "content_writer",
        lambda: ContentWriterAgent(client).run(approved_plan),
        lambda specs: f"Copy written for {len(specs)} posts",
        lambda specs: [s.to_dict() for s in specs],
        lambda d: [CopySpec.from_dict(x) for x in d],
    )
    if on_deliverable is not None:
        on_deliverable("Content Writer", f"Hooks, captions, CTAs for {len(copy_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Visual Designer", "Designing FLUX prompts and color palettes...")
    visual_specs = checkpointed(
        "visual_designer",
        lambda: VisualDesignerAgent(client).run(approved_plan, copy_specs),
        lambda specs: f"Visual specs designed for {len(specs)} posts",
        lambda specs: [s.to_dict() for s in specs],
        lambda d: [VisualSpec.from_dict(x) for x in d],
    )
    if on_deliverable is not None:
        on_deliverable("Visual Designer", f"FLUX prompts, color palettes for {len(visual_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Audio Engineer", "Selecting music tracks and voiceover scripts...")
    audio_specs = checkpointed(
        "audio_engineer",
        lambda: AudioEngineerAgent(client).run(approved_plan, copy_specs),
        lambda specs: f"Audio specs designed for {len(specs)} posts",
        lambda specs: [s.to_dict() for s in specs],
        lambda d: [AudioSpec.from_dict(x) for x in d],
    )
    if on_deliverable is not None:
        on_deliverable("Audio Engineer", f"Music tracks, voiceover scripts for {len(audio_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Video Editor", "Sequencing scenes and transitions...")
    video_specs = checkpointed(
        "video_editor",
        lambda: VideoEditorAgent(client).run(approved_plan, visual_specs, audio_specs),
        lambda specs: f"Video specs designed for {len(specs)} posts",
        lambda specs: [s.to_dict() for s in specs],
        lambda d: [VideoSpec.from_dict(x) for x in d],
    )
    if on_deliverable is not None:
        on_deliverable("Video Editor", f"Scene sequences, transitions for {len(video_specs)} posts")

    if on_agent_activity is not None:
        on_agent_activity("Video Quality Reviewer", "Scoring video quality against the acceptance threshold...")
    video_quality_scores = checkpointed(
        "video_quality_reviewer",
        lambda: VideoQualityReviewerAgent(client).run(video_specs, copy_specs),
        lambda scores: f"Quality scored for {len(scores)} posts, "
                       f"{len(VideoQualityReviewerAgent.needs_regeneration(scores))} flagged for regeneration",
        lambda scores: [s.to_dict() for s in scores],
        lambda d: [VideoQualityScore.from_dict(x) for x in d],
    )
    needs_regeneration = VideoQualityReviewerAgent.needs_regeneration(video_quality_scores)
    if needs_regeneration and on_log is not None:
        on_log("warning", f"Posts flagged for video regeneration: {needs_regeneration}")
    if on_deliverable is not None:
        on_deliverable("Video Quality Reviewer", f"Quality scored for {len(video_quality_scores)} posts"
                                                  + (f"; regeneration flagged: {needs_regeneration}"
                                                     if needs_regeneration else "; all posts passed"))

    if on_agent_activity is not None:
        on_agent_activity("Engagement Strategist", "Writing seed comments and DM triggers...")
    engagement_specs = checkpointed(
        "engagement_strategist",
        lambda: EngagementStrategistAgent(client).run(approved_plan, copy_specs),
        lambda specs: f"Engagement specs designed for {len(specs)} posts",
        lambda specs: [s.to_dict() for s in specs],
        lambda d: [EngagementSpec.from_dict(x) for x in d],
    )
    if on_deliverable is not None:
        on_deliverable("Engagement Strategist", f"Seed comments, DM triggers for {len(engagement_specs)} posts")

    date = approved_plan.date

    artifacts = {
        "approved_plan": approved_plan.to_dict(),
        "analytics_report": analytics_report.to_dict(),
        "trend_report": trend_report.to_dict(),
        "copy": {"items": [c.to_dict() for c in copy_specs]},
        "visual_specs": {"items": [v.to_dict() for v in visual_specs]},
        "audio_specs": {"items": [a.to_dict() for a in audio_specs]},
        "video_specs": {"items": [v.to_dict() for v in video_specs]},
        "video_quality_scores": {"items": [s.to_dict() for s in video_quality_scores]},
        "engagement_specs": {"items": [e.to_dict() for e in engagement_specs]},
    }

    output_paths = {}
    if dry_run:
        if on_log is not None:
            on_log("info", "DRY-RUN: skipping artifact write loop")
    else:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for key, payload in artifacts.items():
            path = _OUTPUT_DIR / f"{key}_{date}.json"
            path.write_text(json.dumps(payload, indent=2))
            output_paths[key] = path

    if on_log is not None:
        on_log("info", "Pipeline complete")

    return {
        "analytics_report": analytics_report,
        "trend_report": trend_report,
        "approved_plan": approved_plan,
        "debate_history": debate_history,
        "copy_specs": copy_specs,
        "visual_specs": visual_specs,
        "audio_specs": audio_specs,
        "video_specs": video_specs,
        "video_quality_scores": video_quality_scores,
        "engagement_specs": engagement_specs,
        "output_paths": output_paths,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the full team chain and save outputs; do not post.")
    parser.add_argument("--resume-from", choices=_STAGE_ORDER, default=None,
                        help="Resume today's run from this stage, loading earlier "
                             "stages from the day's checkpoint file instead of "
                             "re-running (and re-paying for) them.")
    args = parser.parse_args()
    result = run_team_pipeline(dry_run=args.dry_run, resume_from=args.resume_from)
    logger.info(json.dumps({"output_paths": {k: str(v) for k, v in
                      result["output_paths"].items()}}, indent=2))
