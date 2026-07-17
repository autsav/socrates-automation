"""Tests for team.bridge — the module that converts team system output into
pipeline.py's quote_data format."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from team.bridge import (
    load_team_plan,
    load_team_specs,
    team_post_to_quote_data,
    load_team_post,
)
from team.models import ContentPlan, PostPlan, CopySpec, VisualSpec


@pytest.fixture
def sample_plan():
    return ContentPlan(
        date="2026-07-16",
        posts=[
            PostPlan(
                post_number=1, posting_time="08:00", quote_id=42,
                audience="procrastinator", mood="dark_philosophical",
                format="reel", hook_strategy="pattern_interrupt",
                visual_style="dark", audio_strategy="cinematic",
                engagement_strategy="question",
                controversy_question="Are you wasting your potential?",
                cta="Save this as a reminder",
                hashtags=["#stoicism", "#philosophy", "#motivation"],
                estimated_viral_potential=0.75,
                rationale="Morning slot for procrastinators",
            ),
            PostPlan(
                post_number=2, posting_time="14:00", quote_id=43,
                audience="doomscroller", mood="dramatic_ancient",
                format="reel", hook_strategy="question",
                visual_style="epic", audio_strategy="dramatic",
                engagement_strategy="comment",
                controversy_question="What would Socrates say about doomscrolling?",
                cta="Share if this hit home",
                hashtags=["#stoicism", "#socrates"],
                estimated_viral_potential=0.65,
                rationale="Afternoon slot",
            ),
        ],
    )


@pytest.fixture
def sample_copy_specs():
    return [
        CopySpec(
            post_number=1, hook="Stop scrolling. Start questioning everything.",
            caption="You're not lazy. You're just not challenged enough.\n\n— Socrates",
            cta="Save this as a reminder",
            controversy_question="Are you wasting your potential?",
            hashtags=["#stoicism", "#philosophy", "#motivation"],
            carousel_slides=["Slide 1", "Slide 2"],
            story_teaser="Are you wasting your potential?",
        ),
        CopySpec(
            post_number=2, hook="What would Socrates say about your screen time?",
            caption="Doomscrolling won't fix your life. Action will.\n\n— Socrates",
            cta="Share if this hit home",
            controversy_question="What would Socrates say about doomscrolling?",
            hashtags=["#stoicism", "#socrates"],
            carousel_slides=["Slide 1"],
            story_teaser="Screen time vs wisdom",
        ),
    ]


@pytest.fixture
def sample_visual_specs():
    return [
        VisualSpec(
            post_number=1,
            flux_prompt="Dark atmospheric Greek ruins, dramatic lighting, philosophical mood",
            composition_params={"layout": "centered"},
            wallpaper_design={"format": "portrait"},
            carousel_design=[{"slide": 1}],
            color_palette={"primary": "#1a1a2e"},
            font_choice={"family": "Playfair Display"},
        ),
    ]


class TestTeamPostToQuoteData:
    def test_maps_basic_fields(self, sample_plan, sample_copy_specs, sample_visual_specs):
        result = team_post_to_quote_data(sample_plan, sample_copy_specs, sample_visual_specs, slot=0)
        assert result is not None
        assert result["audience"] == "procrastinator"
        assert result["mood"] == "dark_philosophical"
        assert result["row_number"] == 42
        assert result["caption"] == sample_copy_specs[0].caption
        assert result["hook"] == sample_copy_specs[0].hook
        assert result["source"] == "team"
        assert result["format"] == "reel"

    def test_maps_flux_override(self, sample_plan, sample_copy_specs, sample_visual_specs):
        result = team_post_to_quote_data(sample_plan, sample_copy_specs, sample_visual_specs, slot=0)
        assert "flux_override" in result
        assert "Dark atmospheric" in result["flux_override"]

    def test_works_without_visual_specs(self, sample_plan, sample_copy_specs):
        result = team_post_to_quote_data(sample_plan, sample_copy_specs, None, slot=0)
        assert result is not None
        assert "flux_override" not in result

    def test_slot_1_maps_to_post_2(self, sample_plan, sample_copy_specs):
        result = team_post_to_quote_data(sample_plan, sample_copy_specs, None, slot=1)
        assert result is not None
        assert result["audience"] == "doomscroller"
        assert result["row_number"] == 43

    def test_returns_none_for_missing_post(self, sample_plan, sample_copy_specs):
        result = team_post_to_quote_data(sample_plan, sample_copy_specs, None, slot=5)
        assert result is None

    def test_returns_none_for_missing_copy(self, sample_plan):
        result = team_post_to_quote_data(sample_plan, [], None, slot=0)
        assert result is None


class TestLoadTeamPlan:
    def test_returns_none_when_no_file(self, tmp_path):
        with patch("team.bridge._OUTPUT_DIR", tmp_path):
            result = load_team_plan("2026-01-01")
            assert result is None

    def test_loads_plan_from_file(self, tmp_path, sample_plan):
        plan_path = tmp_path / "approved_plan_2026-07-16.json"
        plan_path.write_text(json.dumps(sample_plan.to_dict()))
        with patch("team.bridge._OUTPUT_DIR", tmp_path):
            result = load_team_plan("2026-07-16")
            assert result is not None
            assert result.date == "2026-07-16"
            assert len(result.posts) == 2

    def test_returns_none_on_corrupt_file(self, tmp_path):
        plan_path = tmp_path / "approved_plan_2026-07-16.json"
        plan_path.write_text("{not valid json")
        with patch("team.bridge._OUTPUT_DIR", tmp_path):
            result = load_team_plan("2026-07-16")
            assert result is None


class TestLoadTeamPost:
    def test_full_roundtrip(self, tmp_path, sample_plan, sample_copy_specs, sample_visual_specs):
        # Write all artifacts
        (tmp_path / f"approved_plan_{sample_plan.date}.json").write_text(
            json.dumps(sample_plan.to_dict()))
        (tmp_path / f"copy_{sample_plan.date}.json").write_text(
            json.dumps({"items": [c.to_dict() for c in sample_copy_specs]}))
        (tmp_path / f"visual_specs_{sample_plan.date}.json").write_text(
            json.dumps({"items": [v.to_dict() for v in sample_visual_specs]}))

        with patch("team.bridge._OUTPUT_DIR", tmp_path):
            result = load_team_post(run_date=sample_plan.date, slot=0)
            assert result is not None
            assert result["audience"] == "procrastinator"
            assert result["hook"] == "Stop scrolling. Start questioning everything."

    def test_returns_none_when_no_plan(self, tmp_path):
        with patch("team.bridge._OUTPUT_DIR", tmp_path):
            result = load_team_post(run_date="2026-01-01", slot=0)
            assert result is None