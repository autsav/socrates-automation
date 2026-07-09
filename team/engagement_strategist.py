"""Engagement Strategist agent — turns a ContentPlan + its CopySpecs into
per-post EngagementSpecs.

Mirrors team/visual_designer.py/team/audio_engineer.py: module-level
build_prompt/parse_response helpers (testable without mocking the API) plus a
thin class that wires them to self.client.call.
"""
from __future__ import annotations

import json

from team.base_agent import BaseAgent
from team.models import ContentPlan, CopySpec, EngagementSpec, ENGAGEMENT_SPECS_SCHEMA
from team.prompt_loader import load_prompt
from team.schemas import EngagementSpecsSchema

_PREFIX = (
    "Approved 7-day ContentPlan and its CopySpecs — plan engagement tactics for "
    "every post below, one EngagementSpec per post, matching the plan's assigned "
    "controversy_question/engagement_strategy/audience for that post_number and "
    "seeding comments/replies that reference the real copy written by the content "
    "writer (from the matching CopySpec's controversy_question/caption) rather "
    "than the plan's abstract strategy field alone.\nPlan:\n{plan}\nCopySpecs:\n"
    "{copy_specs}"
)

_USER_CONTENT = "Plan engagement tactics for all 7 posts now."


def build_prompt(plan: ContentPlan, copy_specs: list[CopySpec]) -> str:
    return _PREFIX.format(
        plan=json.dumps(plan.to_dict(), indent=2),
        copy_specs=json.dumps([c.to_dict() for c in copy_specs], indent=2),
    )


def parse_response(d: dict) -> list[EngagementSpec]:
    EngagementSpecsSchema.model_validate(d)
    return [EngagementSpec.from_dict(item) for item in d["items"]]


class EngagementStrategistAgent(BaseAgent):
    def __init__(self, client):
        super().__init__(client)
        self.system_prompt = load_prompt("engagement_strategist")

    def run(self, plan: ContentPlan, copy_specs: list[CopySpec]) -> list[EngagementSpec]:
        shared_prefix = build_prompt(plan, copy_specs)

        return self.call_with_retry("engagement_strategist", shared_prefix, self.system_prompt,
                                    _USER_CONTENT, ENGAGEMENT_SPECS_SCHEMA, parse_response)
