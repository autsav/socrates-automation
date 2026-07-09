import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.visual_designer import VisualDesignerAgent, build_prompt, parse_response
from team.models import ContentPlan, CopySpec, PostPlan, VisualSpec


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def call(self, role, shared_prefix, role_system, user_content, schema):
        self.calls.append({
            "role": role,
            "shared_prefix": shared_prefix,
            "role_system": role_system,
            "user_content": user_content,
            "schema": schema,
        })
        return self.payload


def _post(n, *, format="reel", visual_style="cinematic", mood="dark_philosophical"):
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
        audience="stuck",
        mood=mood,
        format=format,
        hook_strategy="contrarian",
        visual_style=visual_style,
        audio_strategy="lofi build",
        engagement_strategy="seed comment",
        controversy_question="Is discipline overrated?",
        cta="save this",
        hashtags=["#stoic"],
        estimated_viral_potential=7.5,
        rationale="ties to top_performing_hooks",
    )


def _plan(formats=None):
    formats = formats or ["reel"] * 7
    return ContentPlan(
        date="2026-07-09",
        posts=[_post(n, format=fmt) for n, fmt in enumerate(formats, start=1)],
    )


def _copy_spec(n):
    return CopySpec(
        post_number=n,
        hook=f"hook {n}",
        caption=f"caption {n}",
        cta="save this",
        controversy_question="Is discipline overrated?",
        hashtags=["#stoic"],
        carousel_slides=[],
        story_teaser=f"teaser {n}",
    )


def _copy_specs():
    return [_copy_spec(n) for n in range(1, 8)]


def _visual_item(n):
    return {
        "post_number": n,
        "flux_prompt": f"flux prompt {n}",
        "composition_params": {"rule_of_thirds": "left"},
        "wallpaper_design": {"style": "minimal"},
        "carousel_design": [],
        "color_palette": {"primary": "#0f0c0a"},
        "font_choice": {"family": "serif"},
    }


def _visual_payload():
    return {"items": [_visual_item(n) for n in range(1, 8)]}


def test_build_prompt_embeds_plan_and_copy_content():
    plan = _plan()
    copy_specs = _copy_specs()
    prefix = build_prompt(plan, copy_specs)

    assert "dark_philosophical" in prefix
    assert "cinematic" in prefix
    assert "hook 1" in prefix


def test_parse_response_returns_visualspec_list_preserving_order():
    specs = parse_response(_visual_payload())
    assert len(specs) == 7
    assert all(isinstance(s, VisualSpec) for s in specs)
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_builds_correct_visualspec_list_from_mocked_response():
    client = _FakeClient(_visual_payload())
    agent = VisualDesignerAgent(client)

    specs = agent.run(_plan(), _copy_specs())

    assert len(specs) == 7
    assert specs[0].flux_prompt == "flux prompt 1"
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_passes_visual_designer_role_to_client():
    client = _FakeClient(_visual_payload())
    agent = VisualDesignerAgent(client)

    agent.run(_plan(), _copy_specs())

    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "visual_designer"


def test_run_prompt_contains_plan_and_copy_identifying_content():
    client = _FakeClient(_visual_payload())
    agent = VisualDesignerAgent(client)

    plan = _plan()
    copy_specs = _copy_specs()
    agent.run(plan, copy_specs)

    shared_prefix = client.calls[0]["shared_prefix"]
    assert plan.posts[0].mood in shared_prefix
    assert plan.posts[0].visual_style in shared_prefix
    assert copy_specs[0].hook in shared_prefix
