import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.content_writer import ContentWriterAgent, build_prompt, parse_response
from team.models import ContentPlan, CopySpec, PostPlan


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


def _post(n, *, format="reel", hook_strategy="contrarian",
          controversy_question="Is discipline overrated?"):
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
        audience="stuck",
        mood="dark_philosophical",
        format=format,
        hook_strategy=hook_strategy,
        visual_style="cinematic",
        audio_strategy="lofi build",
        engagement_strategy="seed comment",
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


def _copy_item(n):
    return {
        "post_number": n,
        "hook": f"hook {n}",
        "caption": f"caption {n}",
        "cta": "save this",
        "controversy_question": "Is discipline overrated?",
        "hashtags": ["#stoic"],
        "carousel_slides": [],
        "story_teaser": f"teaser {n}",
    }


def _copy_payload():
    return {"items": [_copy_item(n) for n in range(1, 8)]}


def test_build_prompt_embeds_plan_content():
    plan = _plan()
    prefix = build_prompt(plan)
    assert "contrarian" in prefix
    assert "Is discipline overrated?" in prefix
    assert "2026-07-09" in prefix


def test_parse_response_returns_copyspec_list_preserving_order():
    specs = parse_response(_copy_payload())
    assert len(specs) == 7
    assert all(isinstance(s, CopySpec) for s in specs)
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_builds_correct_copyspec_list_from_mocked_response():
    client = _FakeClient(_copy_payload())
    agent = ContentWriterAgent(client)

    specs = agent.run(_plan())

    assert len(specs) == 7
    assert specs[0].hook == "hook 1"
    assert specs[0].caption == "caption 1"
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_passes_content_writer_role_to_client():
    client = _FakeClient(_copy_payload())
    agent = ContentWriterAgent(client)

    agent.run(_plan())

    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "content_writer"


def test_run_prompt_contains_plan_identifying_content():
    client = _FakeClient(_copy_payload())
    agent = ContentWriterAgent(client)

    plan = _plan()
    agent.run(plan)

    shared_prefix = client.calls[0]["shared_prefix"]
    assert plan.posts[0].hook_strategy in shared_prefix
    assert plan.posts[0].controversy_question in shared_prefix


def test_run_handles_carousel_format_post_without_special_code_path():
    formats = ["reel", "carousel", "single", "reel", "carousel", "single", "reel"]
    client = _FakeClient(_copy_payload())
    agent = ContentWriterAgent(client)

    specs = agent.run(_plan(formats=formats))

    assert len(specs) == 7
    shared_prefix = client.calls[0]["shared_prefix"]
    assert "carousel" in shared_prefix

    import inspect
    source = inspect.getsource(ContentWriterAgent.run)
    assert '"carousel"' not in source and "'carousel'" not in source
