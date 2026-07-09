import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from team.reviewer import (
    VideoQualityReviewerAgent,
    build_video_quality_prompt,
    parse_video_quality_response,
    MIN_ACCEPTABLE_SCORE,
)
from team.models import VideoSpec, CopySpec, VideoQualityScore


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


def _video_spec(n):
    return VideoSpec(
        post_number=n,
        scenes=[{"type": "hook"}],
        total_duration=15.0,
        transitions=["wipeleft"],
        motion_effects=["ken_burns_zoom_in"],
        text_overlays=[{"text": "hook text", "start": 0.0}],
        aspect_ratio="9:16",
    )


def _video_specs():
    return [_video_spec(n) for n in range(1, 8)]


def _copy_spec(n):
    return CopySpec(
        post_number=n,
        hook=f"hook {n}",
        caption=f"caption {n}",
        cta="save this",
        controversy_question="Is discipline overrated?",
        hashtags=["#stoic"],
        carousel_slides=[],
        story_teaser="teaser",
    )


def _copy_specs():
    return [_copy_spec(n) for n in range(1, 8)]


def _score_item(n, overall_score=8.0, is_acceptable=True):
    return {
        "post_number": n,
        "visual_appeal": 8,
        "text_readability": 8,
        "content_relevance": 8,
        "production_quality": 8,
        "overall_score": overall_score,
        "is_acceptable": is_acceptable,
        "feedback": "solid",
        "suggestions": "",
    }


def _all_acceptable_payload():
    return {"items": [_score_item(n) for n in range(1, 8)]}


def test_build_video_quality_prompt_embeds_video_and_copy_content():
    prefix = build_video_quality_prompt(_video_specs(), _copy_specs())
    assert "ken_burns_zoom_in" in prefix
    assert "hook 1" in prefix


def test_parse_response_recomputes_is_acceptable_from_threshold():
    payload = {"items": [
        _score_item(1, overall_score=9.0, is_acceptable=False),  # model wrong, should flip to True
        _score_item(2, overall_score=3.0, is_acceptable=True),   # model wrong, should flip to False
    ] + [_score_item(n) for n in range(3, 8)]}

    scores = parse_video_quality_response(payload)

    assert isinstance(scores[0], VideoQualityScore)
    assert scores[0].is_acceptable is True
    assert scores[1].is_acceptable is False


def test_parse_response_threshold_boundary():
    payload = {"items": [_score_item(1, overall_score=MIN_ACCEPTABLE_SCORE)] +
                        [_score_item(n) for n in range(2, 8)]}
    scores = parse_video_quality_response(payload)
    assert scores[0].is_acceptable is True


def test_run_uses_video_quality_reviewer_role_and_is_non_critical():
    client = _FakeClient(_all_acceptable_payload())
    agent = VideoQualityReviewerAgent(client)

    scores = agent.run(_video_specs(), _copy_specs())

    assert len(scores) == 7
    assert all(s.is_acceptable for s in scores)
    assert client.calls[0]["role"] == "video_quality_reviewer"
    assert agent.is_critical is False


def test_needs_regeneration_flags_only_low_scoring_posts():
    payload = {"items": [_score_item(n) for n in range(1, 8)]}
    payload["items"][2]["overall_score"] = 3.0   # post 3
    payload["items"][5]["overall_score"] = 4.5   # post 6

    scores = parse_video_quality_response(payload)
    flagged = VideoQualityReviewerAgent.needs_regeneration(scores)

    assert flagged == [3, 6]


def test_needs_regeneration_empty_when_all_acceptable():
    scores = parse_video_quality_response(_all_acceptable_payload())
    assert VideoQualityReviewerAgent.needs_regeneration(scores) == []
