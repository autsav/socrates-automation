import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.video_editor import VideoEditorAgent, build_prompt, parse_response
from team.models import ContentPlan, VisualSpec, AudioSpec, PostPlan, VideoSpec


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


def _post(n, *, format="reel", mood="dark_philosophical"):
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
        audience="stuck",
        mood=mood,
        format=format,
        hook_strategy="contrarian",
        visual_style="cinematic",
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


def _visual_spec(n):
    return VisualSpec(
        post_number=n,
        flux_prompt=f"flux prompt {n}",
        composition_params={"rule_of_thirds": "left"},
        wallpaper_design={"style": "minimal"},
        carousel_design=[],
        color_palette={"primary": "#0f0c0a"},
        font_choice={"family": "serif"},
    )


def _visual_specs():
    return [_visual_spec(n) for n in range(1, 8)]


def _audio_spec(n):
    return AudioSpec(
        post_number=n,
        music_track=f"track {n}",
        voiceover_text=f"voiceover {n}",
        voiceover_emotion="urgent",
        beat_markers=[0.5, 1.5],
        mix_levels={"voice": 0, "music": -12},
        jingle=False,
    )


def _audio_specs():
    return [_audio_spec(n) for n in range(1, 8)]


def _video_item(n):
    return {
        "post_number": n,
        "scenes": [{"type": "hook"}],
        "total_duration": 15.0,
        "transitions": ["wipeleft"],
        "motion_effects": ["ken_burns_zoom_in"],
        "text_overlays": [{"text": "hook text", "start": 0.0}],
        "aspect_ratio": "9:16",
    }


def _video_payload():
    return {"items": [_video_item(n) for n in range(1, 8)]}


def test_build_prompt_embeds_plan_visual_and_audio_content():
    plan = _plan()
    visual_specs = _visual_specs()
    audio_specs = _audio_specs()
    prefix = build_prompt(plan, visual_specs, audio_specs)

    assert "reel" in prefix
    assert "flux prompt 1" in prefix
    assert "voiceover 1" in prefix


def test_parse_response_returns_videospec_list_preserving_order():
    specs = parse_response(_video_payload())
    assert len(specs) == 7
    assert all(isinstance(s, VideoSpec) for s in specs)
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_builds_correct_videospec_list_from_mocked_response():
    client = _FakeClient(_video_payload())
    agent = VideoEditorAgent(client)

    specs = agent.run(_plan(), _visual_specs(), _audio_specs())

    assert len(specs) == 7
    assert specs[0].total_duration == 15.0
    assert [s.post_number for s in specs] == list(range(1, 8))


def test_run_passes_video_editor_role_to_client():
    client = _FakeClient(_video_payload())
    agent = VideoEditorAgent(client)

    agent.run(_plan(), _visual_specs(), _audio_specs())

    assert len(client.calls) == 1
    assert client.calls[0]["role"] == "video_editor"


def test_run_prompt_contains_plan_visual_and_audio_identifying_content():
    client = _FakeClient(_video_payload())
    agent = VideoEditorAgent(client)

    plan = _plan()
    visual_specs = _visual_specs()
    audio_specs = _audio_specs()
    agent.run(plan, visual_specs, audio_specs)

    shared_prefix = client.calls[0]["shared_prefix"]
    assert plan.posts[0].format in shared_prefix
    assert visual_specs[0].flux_prompt in shared_prefix
    assert audio_specs[0].beat_markers[0].__str__() in shared_prefix or "0.5" in shared_prefix
    assert audio_specs[0].voiceover_text in shared_prefix


def test_run_handles_non_reel_format_post_without_special_code_path():
    formats = ["reel", "carousel", "single", "reel", "carousel", "single", "reel"]
    client = _FakeClient(_video_payload())
    agent = VideoEditorAgent(client)

    specs = agent.run(_plan(formats=formats), _visual_specs(), _audio_specs())

    assert len(specs) == 7
    shared_prefix = client.calls[0]["shared_prefix"]
    assert "carousel" in shared_prefix

    import inspect
    source = inspect.getsource(VideoEditorAgent.run)
    assert '"carousel"' not in source and "'carousel'" not in source
    assert '"single"' not in source and "'single'" not in source
    assert '"reel"' not in source and "'reel'" not in source
