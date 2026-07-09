import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.models import (
    PostPlan, ContentPlan, DebateResult, CopySpec, VisualSpec, AudioSpec,
    VideoSpec, EngagementSpec, AnalyticsReport,
    POST_PLAN_ITEM_SCHEMA, CONTENT_PLAN_SCHEMA, REVIEWER_OUTPUT_SCHEMA,
    COPY_SPEC_ITEM_SCHEMA, COPY_SPECS_SCHEMA,
    VISUAL_SPEC_ITEM_SCHEMA, VISUAL_SPECS_SCHEMA,
    AUDIO_SPEC_ITEM_SCHEMA, AUDIO_SPECS_SCHEMA,
    VIDEO_SPEC_ITEM_SCHEMA, VIDEO_SPECS_SCHEMA,
    ENGAGEMENT_SPEC_ITEM_SCHEMA, ENGAGEMENT_SPECS_SCHEMA,
    ANALYTICS_REPORT_SCHEMA,
)


def _make_post_plan(post_number=1):
    return PostPlan(
        post_number=post_number,
        posting_time="08:00",
        quote_id=42,
        audience="procrastinator",
        mood="epic_warrior",
        format="reel",
        hook_strategy="pattern_interrupt",
        visual_style="dark academia",
        audio_strategy="trending_audio",
        engagement_strategy="ask_question",
        controversy_question="Is discipline overrated?",
        cta="Save this.",
        hashtags=["#stoicism", "#discipline"],
        estimated_viral_potential=0.82,
        rationale="strong hook + trending audio",
    )


def _make_content_plan():
    return ContentPlan(date="2026-07-09", posts=[_make_post_plan(1), _make_post_plan(2)])


def _make_debate_result():
    plan = _make_content_plan()
    return DebateResult(
        round_number=1,
        planner_output=json.dumps(plan.to_dict()),
        reviewer_output=json.dumps({"score": 8.5, "approved": True}),
        reviewer_score=8.5,
        approved=True,
        final_plan=plan,
    )


def _make_copy_spec():
    return CopySpec(
        post_number=1,
        hook="You already know the answer.",
        caption="Long caption text here.",
        cta="Save this.",
        controversy_question="Is discipline overrated?",
        hashtags=["#stoicism"],
        carousel_slides=["slide 1", "slide 2"],
        story_teaser="teaser text",
    )


def _make_visual_spec():
    return VisualSpec(
        post_number=1,
        flux_prompt="a marble statue at dawn",
        composition_params={"rule_of_thirds": True},
        wallpaper_design={"bg": "dark"},
        carousel_design=[{"slide": 1}, {"slide": 2}],
        color_palette={"primary": "#000000"},
        font_choice={"family": "Cinzel"},
    )


def _make_audio_spec():
    return AudioSpec(
        post_number=1,
        music_track="track_01.mp3",
        voiceover_text="Discipline is destiny.",
        voiceover_emotion="stoic",
        beat_markers=[0.5, 1.0, 1.5],
        mix_levels={"voice": 0.8, "music": 0.4},
        jingle=False,
    )


def _make_video_spec():
    return VideoSpec(
        post_number=1,
        scenes=[{"scene": 1}, {"scene": 2}],
        total_duration=15.5,
        transitions=["fade", "cut"],
        motion_effects=["ken_burns"],
        text_overlays=[{"text": "Discipline"}],
        aspect_ratio="9:16",
    )


def _make_engagement_spec():
    return EngagementSpec(
        post_number=1,
        seed_comments=["This hit different.", "Needed this today."],
        reply_templates=["Glad it resonated!"],
        dm_trigger="DM 'STOIC' for the full guide",
        save_bait_frame="frame_03.jpg",
        story_teaser="teaser",
        highlight_category="discipline",
    )


def _make_analytics_report():
    return AnalyticsReport(
        date="2026-07-09",
        total_posts=3,
        avg_engagement_rate=0.045,
        top_performing_hooks=["pattern_interrupt"],
        top_performing_moods=["epic_warrior"],
        best_posting_times=["08:00"],
        worst_performing_content=["post_2"],
        recommendations=["post more reels"],
        follower_growth=120,
        save_rate=0.12,
    )


def test_post_plan_roundtrip():
    p = _make_post_plan()
    assert PostPlan.from_dict(p.to_dict()) == p


def test_content_plan_roundtrip_nested():
    plan = _make_content_plan()
    round_tripped = ContentPlan.from_dict(plan.to_dict())
    assert round_tripped == plan
    assert all(isinstance(post, PostPlan) for post in round_tripped.posts)


def test_debate_result_roundtrip_nested():
    result = _make_debate_result()
    round_tripped = DebateResult.from_dict(result.to_dict())
    assert round_tripped == result
    assert isinstance(round_tripped.final_plan, ContentPlan)
    assert isinstance(round_tripped.final_plan.posts[0], PostPlan)


def test_copy_spec_roundtrip():
    c = _make_copy_spec()
    assert CopySpec.from_dict(c.to_dict()) == c


def test_visual_spec_roundtrip():
    v = _make_visual_spec()
    assert VisualSpec.from_dict(v.to_dict()) == v


def test_audio_spec_roundtrip():
    a = _make_audio_spec()
    assert AudioSpec.from_dict(a.to_dict()) == a


def test_video_spec_roundtrip():
    v = _make_video_spec()
    assert VideoSpec.from_dict(v.to_dict()) == v


def test_engagement_spec_roundtrip():
    e = _make_engagement_spec()
    assert EngagementSpec.from_dict(e.to_dict()) == e


def test_analytics_report_roundtrip():
    r = _make_analytics_report()
    assert AnalyticsReport.from_dict(r.to_dict()) == r


ALL_SCHEMAS = {
    "POST_PLAN_ITEM_SCHEMA": POST_PLAN_ITEM_SCHEMA,
    "CONTENT_PLAN_SCHEMA": CONTENT_PLAN_SCHEMA,
    "REVIEWER_OUTPUT_SCHEMA": REVIEWER_OUTPUT_SCHEMA,
    "COPY_SPEC_ITEM_SCHEMA": COPY_SPEC_ITEM_SCHEMA,
    "COPY_SPECS_SCHEMA": COPY_SPECS_SCHEMA,
    "VISUAL_SPEC_ITEM_SCHEMA": VISUAL_SPEC_ITEM_SCHEMA,
    "VISUAL_SPECS_SCHEMA": VISUAL_SPECS_SCHEMA,
    "AUDIO_SPEC_ITEM_SCHEMA": AUDIO_SPEC_ITEM_SCHEMA,
    "AUDIO_SPECS_SCHEMA": AUDIO_SPECS_SCHEMA,
    "VIDEO_SPEC_ITEM_SCHEMA": VIDEO_SPEC_ITEM_SCHEMA,
    "VIDEO_SPECS_SCHEMA": VIDEO_SPECS_SCHEMA,
    "ENGAGEMENT_SPEC_ITEM_SCHEMA": ENGAGEMENT_SPEC_ITEM_SCHEMA,
    "ENGAGEMENT_SPECS_SCHEMA": ENGAGEMENT_SPECS_SCHEMA,
    "ANALYTICS_REPORT_SCHEMA": ANALYTICS_REPORT_SCHEMA,
}


def test_all_schemas_are_strict_objects():
    for name, schema in ALL_SCHEMAS.items():
        assert isinstance(schema, dict), name
        assert schema["type"] == "object", name
        assert schema["additionalProperties"] is False, name
        assert set(schema["properties"].keys()) == set(schema["required"]), name


def test_post_plan_schema_has_all_15_fields_required():
    assert len(POST_PLAN_ITEM_SCHEMA["required"]) == 15
    assert POST_PLAN_ITEM_SCHEMA["properties"]["hashtags"] == {
        "type": "array", "items": {"type": "string"}}


def test_analytics_report_schema_has_all_10_fields_required():
    assert len(ANALYTICS_REPORT_SCHEMA["required"]) == 10


def test_json_dumps_all_instances():
    instances = [
        _make_post_plan(), _make_content_plan(), _make_debate_result(),
        _make_copy_spec(), _make_visual_spec(), _make_audio_spec(),
        _make_video_spec(), _make_engagement_spec(), _make_analytics_report(),
    ]
    for inst in instances:
        json.dumps(inst.to_dict())
