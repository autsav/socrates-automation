"""Visual Designer agent — turns a ContentPlan + its CopySpecs into per-post VisualSpecs.

Mirrors team/content_writer.py: module-level build_prompt/parse_response helpers
(testable without mocking the API) plus a thin class that wires them to
self.client.call.
"""
from __future__ import annotations

import json

from team.models import ContentPlan, CopySpec, VisualSpec, VISUAL_SPECS_SCHEMA
from team.prompt_loader import load_prompt

_PREFIX = (
    "Approved 7-day ContentPlan and its CopySpecs — design the visuals for every post "
    "below, one VisualSpec per post, matching the plan's assigned mood/visual_style/"
    "format for that post_number and composing around that post's hook text (from the "
    "matching CopySpec) rather than inventing your own direction.\nPlan:\n{plan}\n"
    "CopySpecs:\n{copy_specs}"
)

_USER_CONTENT = "Design the visuals for all 7 posts now."


def build_prompt(plan: ContentPlan, copy_specs: list[CopySpec]) -> str:
    return _PREFIX.format(
        plan=json.dumps(plan.to_dict(), indent=2),
        copy_specs=json.dumps([c.to_dict() for c in copy_specs], indent=2),
    )


def parse_response(d: dict) -> list[VisualSpec]:
    return [VisualSpec.from_dict(item) for item in d["items"]]


class VisualDesignerAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("visual_designer")

    def run(self, plan: ContentPlan, copy_specs: list[CopySpec]) -> list[VisualSpec]:
        shared_prefix = build_prompt(plan, copy_specs)

        data = self.client.call("visual_designer", shared_prefix, self.system_prompt,
                                _USER_CONTENT, VISUAL_SPECS_SCHEMA)
        return parse_response(data)
