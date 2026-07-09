import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.audio_engineer import AudioEngineerAgent, build_prompt, parse_response
from team.models import ContentPlan, CopySpec, PostPlan, AudioSpec


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


def _post(n, *, format="reel", audio_strategy="lofi build", mood="dark_philosophical"):
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
        audience="stuck",
        mood=mood,
        format=format,
        hook_strategy="contrarian",
        visual_style="cinematic",
        audio_strategy=audio_strategy,
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


def _audio_item(n):
    return {
        "post_number": n,
        "music_track": f"track {n}",
        "voiceover_text": f"voiceover {n}",
        "voiceover_emotion": "urgent",
        "beat_markers": [0.5, 1.5],
        "mix_levels": {"voice": 0, "music": -12},
        "jingle": False,
    }


def _audio_payload():
    return {"items": [_audio_item(n) for n in range(1, 8)]}


def test_build_prompt_embeds_plan_and_copy_content():
    plan = _plan()
    copy_specs = _copy_specs()
    prefix = build_prompt(plan, copy_specs)

    assert "dark_philosophical" in prefix
    assert "lofi build" in prefix
    assert "hook 1" in prefix
    assert "caption 1" in prefix


def test_parse_response_returns_audiospec_list_preserving_order():
    specs = parse_response(_audio_payload())
    assert len(specs) == 7
    assert all(isinstance(s, AudioSpec) for s in specs)
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_builds_correct_audiospec_list_from_mocked_response():
    client = _FakeClient(_audio_payload())
    agent = AudioEngineerAgent(client)

    specs = agent.run(_plan(), _copy_specs())

    assert len(specs) == 7
    assert specs[0].music_track == "track 1"
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_passes_audio_engineer_role_to_client():
    client = _FakeClient(_audio_payload())
    agent = AudioEngineerAgent(client)

    agent.run(_plan(), _copy_specs())

    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "audio_engineer"


def test_run_prompt_contains_plan_and_copy_identifying_content():
    client = _FakeClient(_audio_payload())
    agent = AudioEngineerAgent(client)

    plan = _plan()
    copy_specs = _copy_specs()
    agent.run(plan, copy_specs)

    shared_prefix = client.calls[0]["shared_prefix"]
    assert plan.posts[0].mood in shared_prefix
    assert plan.posts[0].audio_strategy in shared_prefix
    assert copy_specs[0].hook in shared_prefix
    assert copy_specs[0].caption in shared_prefix
