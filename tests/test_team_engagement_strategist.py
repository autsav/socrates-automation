import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.engagement_strategist import (
    EngagementStrategistAgent, build_prompt, parse_response,
)
from team.models import ContentPlan, CopySpec, PostPlan, EngagementSpec


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


def _post(n, *, format="reel", engagement_strategy="seed comment",
          controversy_question="Is discipline overrated?"):
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
        audience="stuck",
        mood="dark_philosophical",
        format=format,
        hook_strategy="contrarian",
        visual_style="cinematic",
        audio_strategy="lofi build",
        engagement_strategy=engagement_strategy,
        controversy_question=controversy_question,
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
        controversy_question=f"controversy question {n}",
        hashtags=["#stoic"],
        carousel_slides=[],
        story_teaser=f"teaser {n}",
    )


def _copy_specs():
    return [_copy_spec(n) for n in range(1, 8)]


def _engagement_item(n):
    return {
        "post_number": n,
        "seed_comments": [f"seed comment {n}"],
        "reply_templates": [f"reply template {n}"],
        "dm_trigger": f"trigger {n}",
        "save_bait_frame": f"frame {n}",
        "story_teaser": f"story teaser {n}",
        "highlight_category": "Wisdom",
    }


def _engagement_payload():
    return {"items": [_engagement_item(n) for n in range(1, 8)]}


def test_build_prompt_embeds_plan_and_copy_content():
    plan = _plan()
    copy_specs = _copy_specs()
    prefix = build_prompt(plan, copy_specs)

    assert "seed comment" in prefix
    assert "controversy question 1" in prefix
    assert "caption 1" in prefix


def test_parse_response_returns_engagementspec_list_preserving_order():
    specs = parse_response(_engagement_payload())
    assert len(specs) == 7
    assert all(isinstance(s, EngagementSpec) for s in specs)
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_builds_correct_engagementspec_list_from_mocked_response():
    client = _FakeClient(_engagement_payload())
    agent = EngagementStrategistAgent(client)

    specs = agent.run(_plan(), _copy_specs())

    assert len(specs) == 7
    assert specs[0].dm_trigger == "trigger 1"
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_passes_engagement_strategist_role_to_client():
    client = _FakeClient(_engagement_payload())
    agent = EngagementStrategistAgent(client)

    agent.run(_plan(), _copy_specs())

    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "engagement_strategist"


def test_run_prompt_contains_plan_and_copy_identifying_content():
    client = _FakeClient(_engagement_payload())
    agent = EngagementStrategistAgent(client)

    plan = _plan()
    copy_specs = _copy_specs()
    agent.run(plan, copy_specs)

    shared_prefix = client.calls[0]["shared_prefix"]
    assert plan.posts[0].controversy_question in shared_prefix
    assert plan.posts[0].engagement_strategy in shared_prefix
    assert copy_specs[0].controversy_question in shared_prefix
    assert copy_specs[0].caption in shared_prefix


def test_run_handles_non_reel_format_post_without_special_code_path():
    formats = ["reel", "carousel", "single", "reel", "carousel", "single", "reel"]
    client = _FakeClient(_engagement_payload())
    agent = EngagementStrategistAgent(client)

    specs = agent.run(_plan(formats=formats), _copy_specs())

    assert len(specs) == 7
    shared_prefix = client.calls[0]["shared_prefix"]
    assert "carousel" in shared_prefix

    import inspect
    source = inspect.getsource(EngagementStrategistAgent.run)
    assert '"carousel"' not in source and "'carousel'" not in source
    assert '"single"' not in source and "'single'" not in source
    assert '"reel"' not in source and "'reel'" not in source
