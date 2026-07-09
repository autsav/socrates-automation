"""Video Editor agent — turns a ContentPlan + its VisualSpecs/AudioSpecs into
per-post VideoSpecs.

Mirrors team/visual_designer.py/team/audio_engineer.py: module-level
build_prompt/parse_response helpers (testable without mocking the API) plus a
thin class that wires them to self.client.call.

Only reel-format posts need real scene/transition/motion-effect detail —
carousel and single posts don't have video. That distinction is left entirely
to the prompt (each post's `format` is embedded in the plan) rather than
branched on in code; for non-reel posts the model is expected to return a
minimal/trivial VideoSpec (e.g. empty `scenes`, `total_duration: 0.0`).
"""
from __future__ import annotations

import json

from team.models import ContentPlan, VisualSpec, AudioSpec, VideoSpec, VIDEO_SPECS_SCHEMA
from team.prompt_loader import load_prompt

_PREFIX = (
    "Approved 7-day ContentPlan and its VisualSpecs/AudioSpecs — edit the video for "
    "every post below, one VideoSpec per post, matching the plan's assigned format "
    "for that post_number. Only reel-format posts need real scene/transition/"
    "motion-effect detail — carousel and single posts don't have video, so return a "
    "minimal/trivial VideoSpec (e.g. empty scenes, total_duration 0.0) for those. "
    "Compose scenes/motion around what's actually on screen (from the matching "
    "VisualSpec's flux_prompt/wallpaper_design) and sync transitions/text-overlay "
    "timing to what the video must sync to (from the matching AudioSpec's "
    "beat_markers/voiceover_text) rather than inventing your own direction.\n"
    "Plan:\n{plan}\nVisualSpecs:\n{visual_specs}\nAudioSpecs:\n{audio_specs}"
)

_USER_CONTENT = "Edit the video plan for all 7 posts now."


def build_prompt(plan: ContentPlan, visual_specs: list[VisualSpec],
                  audio_specs: list[AudioSpec]) -> str:
    return _PREFIX.format(
        plan=json.dumps(plan.to_dict(), indent=2),
        visual_specs=json.dumps([v.to_dict() for v in visual_specs], indent=2),
        audio_specs=json.dumps([a.to_dict() for a in audio_specs], indent=2),
    )


def parse_response(d: dict) -> list[VideoSpec]:
    return [VideoSpec.from_dict(item) for item in d["items"]]


class VideoEditorAgent:
    def __init__(self, client):
        self.client = client
        self.system_prompt = load_prompt("video_editor")

    def run(self, plan: ContentPlan, visual_specs: list[VisualSpec],
            audio_specs: list[AudioSpec]) -> list[VideoSpec]:
        shared_prefix = build_prompt(plan, visual_specs, audio_specs)

        data = self.client.call("video_editor", shared_prefix, self.system_prompt,
                                _USER_CONTENT, VIDEO_SPECS_SCHEMA)
        return parse_response(data)
