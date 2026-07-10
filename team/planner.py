"""Planner agent — produces/revises the 7-day ContentPlan.

Mirrors studio/strategist.py: module-level build_prompt/parse_response helpers
(testable without mocking the API) plus a thin class that wires them to
self.client.call. Round-counting and the >=8.0 approval threshold live in the
later team/debate.py — this agent only produces or revises a single plan.

Viral-growth note: the account posts 6x/day (`.github/workflows/daily_post.yml`),
split between zero-cost POV text Reels (`src/video/pov_reel_generator.py`) and
regular FLUX Reels. That cadence is driven by the cron schedule, not by this
plan's shape — ContentPlan stays one PostPlan per day (validated 1..7 by
team/schemas.py across every downstream spec), but `team/prompts/planner.md`
now biases `format`/`visual_style` toward the cheap, high-volume POV
treatment. See POV_PRIORITY_HINT below.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from team.base_agent import BaseAgent
from team.models import AnalyticsReport, ContentPlan, CONTENT_PLAN_SCHEMA
from team.prompt_loader import load_prompt
from team.schemas import ContentPlanSchema

# Reinforces team/prompts/planner.md's "POV Reels are the priority format"
# section directly in the user turn (this codebase's existing pattern for
# high-priority constraints — see _FEEDBACK_ADDENDUM below).
POV_PRIORITY_HINT = (
    "Reminder: POV text Reels (black background, oversized centered hook/quote/CTA "
    "text, ffmpeg+Pillow, zero marginal cost) are this account's priority format at "
    "the current 6x/day posting volume. Bias reel-format posts toward a POV-style "
    "visual_style/hook_strategy when analytics support it, and say so in rationale."
)

_PREFIX = (
    "Plan start date (the plan covers the 7 days beginning this date): {plan_date}\n"
    "Analytics report to ground this plan:\n{analytics}\n"
    "Available quotes pool — pick from these only; for each post set quote_id "
    "to the chosen quote's row_number:\n{pool}\n"
    f"{POV_PRIORITY_HINT}"
)

_FEEDBACK_ADDENDUM = (
    "\n\nThis is a REVISION round, not the first draft. The reviewer's critique "
    "of your previous plan was:\n{feedback}\n"
    "You must materially address this feedback in your revision — rewrite the "
    "specific posts/fields the reviewer flagged. Do not resubmit the prior "
    "plan unchanged or with only cosmetic word-swaps."
)

_USER_FIRST_ROUND = "Produce the 7-day ContentPlan now."
_USER_REVISION_ROUND = (
    "Revise the 7-day ContentPlan now, materially addressing the reviewer "
    "feedback given above."
)


def build_prompt(analytics_report: AnalyticsReport, quotes_pool: list[dict],
                  plan_date: str, *, feedback: str | None = None) -> str:
    prefix = _PREFIX.format(
        plan_date=plan_date,
        analytics=json.dumps(analytics_report.to_dict(), indent=2),
        pool=json.dumps(
            [{"row_number": q["row_number"], "quote": q["quote"],
              "audience": q.get("audience", "")} for q in quotes_pool],
            indent=2),
    )
    if feedback is not None:
        prefix += _FEEDBACK_ADDENDUM.format(feedback=feedback)
    return prefix


def parse_response(d: dict) -> ContentPlan:
    ContentPlanSchema.model_validate(d)
    return ContentPlan.from_dict(d)


class PlannerAgent(BaseAgent):
    def __init__(self, client):
        super().__init__(client)
        self.system_prompt = load_prompt("planner")

    def run(self, analytics_report: AnalyticsReport, quotes_pool: list[dict],
            *, feedback: str | None = None, now: datetime | None = None) -> ContentPlan:
        now = now or datetime.utcnow()
        plan_date = (now + timedelta(days=1)).date().isoformat()

        shared_prefix = build_prompt(analytics_report, quotes_pool, plan_date,
                                     feedback=feedback)
        user_content = _USER_REVISION_ROUND if feedback is not None else _USER_FIRST_ROUND

        plan = self.call_with_retry("planner", shared_prefix, self.system_prompt,
                                    user_content, CONTENT_PLAN_SCHEMA, parse_response)
        plan.date = plan_date
        return plan
