"""Content Writer agent — turns an approved ContentPlan into per-post CopySpecs.

Mirrors team/planner.py/team/analytics_analyst.py: module-level build_prompt/
parse_response helpers (testable without mocking the API) plus a thin class that
wires them to self.client.call.
"""
from __future__ import annotations

import json

from team.models import ContentPlan, CopySpec, COPY_SPECS_SCHEMA
from team.prompt_loader import load_prompt

_PREFIX = (
    "Approved 7-day ContentPlan — write copy for every post below, one CopySpec "
    "per post, matching the plan's assigned hook_strategy/audience/mood/format "
    "for that post_number rather than inventing your own direction. Each post's "
    "`format` field is 'reel', 'carousel', or 'single' — only populate "
    "carousel_slides with real content when format == 'carousel'; an empty list "
    "is fine for reel/single posts.\n{plan}"
)

_USER_CONTENT = "Write the copy for all 7 posts now."


def build_prompt(plan: ContentPlan) -> str:
    return _PREFIX.format(plan=json.dumps(plan.to_dict(), indent=2))


def parse_response(d: dict) -> list[CopySpec]:
    return [CopySpec.from_dict(item) for item in d["items"]]


class ContentWriterAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("content_writer")

    def run(self, plan: ContentPlan) -> list[CopySpec]:
        shared_prefix = build_prompt(plan)

        data = self.client.call("content_writer", shared_prefix, self.system_prompt,
                                _USER_CONTENT, COPY_SPECS_SCHEMA)
        return parse_response(data)
