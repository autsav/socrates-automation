"""Reviewer agent — critiques a ContentPlan and returns a raw score dict.

Mirrors studio/director.py's build_prompt/parse_response separation. The
LLM's own `approved` field is advisory only: team/debate.py (a later task)
independently decides approval via score >= 8.0, so no threshold logic lives
here — this agent just returns what the model said.
"""
from __future__ import annotations

import json

from team.base_agent import BaseAgent
from team.models import AnalyticsReport, ContentPlan, REVIEWER_OUTPUT_SCHEMA
from team.prompt_loader import load_prompt
from team.schemas import ReviewerOutputSchema

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
