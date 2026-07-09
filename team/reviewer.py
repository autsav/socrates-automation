"""Reviewer agents — critique a ContentPlan, and separately score VideoSpec quality.

ReviewerAgent mirrors studio/director.py's build_prompt/parse_response
separation. The LLM's own `approved` field is advisory only: team/debate.py
independently decides approval via score >= 8.0, so no threshold logic lives
here — this agent just returns what the model said.

VideoQualityReviewerAgent follows the same advisory-field convention: the
model's own `is_acceptable` guess is discarded and recomputed in
parse_video_quality_response() from MIN_ACCEPTABLE_SCORE, so the accept/
regenerate decision is deterministic given the model's overall_score rather
than dependent on the model correctly applying the threshold itself. It is
non-critical (BaseAgent.is_critical = False) — a scoring failure should never
block the pipeline the way a plan-approval failure does. Not yet wired into
team/orchestrator.py; needs_regeneration() is the regeneration-trigger hook a
future task would call after team/video_editor.py runs.
"""
from __future__ import annotations

import json

from team.base_agent import BaseAgent
from team.models import (
    AnalyticsReport, ContentPlan, CopySpec, VideoSpec, VideoQualityScore,
    REVIEWER_OUTPUT_SCHEMA, VIDEO_QUALITY_SCORES_SCHEMA,
)
from team.prompt_loader import load_prompt
from team.schemas import ReviewerOutputSchema, VideoQualityScoresSchema

_PREFIX = (
    "Content plan to review:\n{plan}\n"
    "Analytics report context (what's actually winning/dying for this account):\n"
    "{analytics}"
)

_USER_CONTENT = "Review this plan now."


def build_prompt(plan: ContentPlan, analytics_report: AnalyticsReport) -> str:
    return _PREFIX.format(
        plan=json.dumps(plan.to_dict(), indent=2),
        analytics=json.dumps(analytics_report.to_dict(), indent=2),
    )


def parse_response(d: dict) -> dict:
    ReviewerOutputSchema.model_validate(d)
    return d


class ReviewerAgent(BaseAgent):
    def __init__(self, client):
        super().__init__(client)
        self.system_prompt = load_prompt("reviewer")

    def run(self, plan: ContentPlan, analytics_report: AnalyticsReport) -> dict:
        shared_prefix = build_prompt(plan, analytics_report)
        return self.call_with_retry("reviewer", shared_prefix, self.system_prompt,
                                    _USER_CONTENT, REVIEWER_OUTPUT_SCHEMA, parse_response)


# Overall score at or above this is acceptable — below it, needs_regeneration()
# flags the post. Matches agent-content-kit's VideoQualityAgent.MIN_ACCEPTABLE_SCORE.
MIN_ACCEPTABLE_SCORE = 5.5

_VIDEO_QUALITY_PREFIX = (
    "VideoSpecs to quality-review:\n{video_specs}\n"
    "CopySpecs for content-relevance grounding (hook/caption/cta each VideoSpec must match):\n"
    "{copy_specs}"
)

_VIDEO_QUALITY_USER_CONTENT = "Score the video quality for all 7 posts now."


def build_video_quality_prompt(video_specs: list[VideoSpec], copy_specs: list[CopySpec]) -> str:
    return _VIDEO_QUALITY_PREFIX.format(
        video_specs=json.dumps([v.to_dict() for v in video_specs], indent=2),
        copy_specs=json.dumps([c.to_dict() for c in copy_specs], indent=2),
    )


def parse_video_quality_response(d: dict) -> list[VideoQualityScore]:
    VideoQualityScoresSchema.model_validate(d)
    scores = []
    for item in d["items"]:
        item = dict(item)
        item["is_acceptable"] = item["overall_score"] >= MIN_ACCEPTABLE_SCORE
        scores.append(VideoQualityScore.from_dict(item))
    return scores


class VideoQualityReviewerAgent(BaseAgent):
    is_critical = False

    def __init__(self, client):
        super().__init__(client)
        self.system_prompt = load_prompt("video_quality")

    def run(self, video_specs: list[VideoSpec], copy_specs: list[CopySpec]) -> list[VideoQualityScore]:
        shared_prefix = build_video_quality_prompt(video_specs, copy_specs)
        return self.call_with_retry(
            "video_quality_reviewer", shared_prefix, self.system_prompt,
            _VIDEO_QUALITY_USER_CONTENT, VIDEO_QUALITY_SCORES_SCHEMA,
            parse_video_quality_response,
        )

    @staticmethod
    def needs_regeneration(scores: list[VideoQualityScore]) -> list[int]:
        """post_numbers whose overall_score fell below MIN_ACCEPTABLE_SCORE —
        the regeneration trigger borrowed from agent-content-kit's VideoQualityAgent."""
        return [s.post_number for s in scores if not s.is_acceptable]
