import inspect
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import team.orchestrator as orchestrator
from team.models import (
    AnalyticsReport, ContentPlan, PostPlan, DebateResult,
    CopySpec, VisualSpec, AudioSpec, VideoSpec, EngagementSpec,
)


# ── canned fixtures ──────────────────────────────────────────────────────────

def _analytics_report():
    return AnalyticsReport(
        date="2026-07-09",
        total_posts=10,
        avg_engagement_rate=0.05,
        top_performing_hooks=["hook_a"],
        top_performing_moods=["dark_philosophical"],
        best_posting_times=["07:00"],
        worst_performing_content=["hook_z"],
        recommendations=["Post more at 07:00"],
        follower_growth=100,
        save_rate=0.02,
    )


def _post(n):
    return PostPlan(
        post_number=n,
        posting_time="07:00",
        quote_id=n,
        audience="stuck",
        mood="dark_philosophical",
        format="reel",
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


def _plan(date="2026-07-09"):
    return ContentPlan(date=date, posts=[_post(n) for n in range(1, 8)])


def _debate_history(plan):
    return [DebateResult(
        round_number=1,
        planner_output=json.dumps(plan.to_dict()),
        reviewer_output=json.dumps({"score": 9.0}),
        reviewer_score=9.0,
        approved=True,
        final_plan=plan,
    )]


def _copy_specs():
    return [CopySpec(
        post_number=n, hook="hook", caption="caption", cta="cta",
        controversy_question="q?", hashtags=["#a"], carousel_slides=["slide"],
        story_teaser="teaser",
    ) for n in range(1, 8)]


def _visual_specs():
    return [VisualSpec(
        post_number=n, flux_prompt="prompt", composition_params={},
        wallpaper_design={}, carousel_design=[{}], color_palette={},
        font_choice={},
    ) for n in range(1, 8)]


def _audio_specs():
    return [AudioSpec(
        post_number=n, music_track="track", voiceover_text="text",
        voiceover_emotion="calm", beat_markers=[1.0], mix_levels={},
        jingle=False,
    ) for n in range(1, 8)]


def _video_specs():
    return [VideoSpec(
        post_number=n, scenes=[{}], total_duration=30.0, transitions=["cut"],
        motion_effects=["kenburns"], text_overlays=[{}], aspect_ratio="9:16",
    ) for n in range(1, 8)]


def _engagement_specs():
    return [EngagementSpec(
        post_number=n, seed_comments=["comment"], reply_templates=["reply"],
        dm_trigger="trigger", save_bait_frame="frame", story_teaser="teaser",
        highlight_category="category",
    ) for n in range(1, 8)]


def _tracked_class(name, return_value, call_log):
    """Mock class whose construction and .run() both append to call_log,
    so tests can assert dependency order across the whole chain."""
    instance = Mock(name=f"{name}_instance")
    instance.run = Mock(side_effect=lambda *a, **k: (
        call_log.append((f"{name}.run", a, k)), return_value)[1])
    cls = Mock(name=name, side_effect=lambda *a, **k: (
        call_log.append((f"{name}.__init__", a, k)), instance)[1])
    return cls, instance


class Harness:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.call_log = []
        self.plan = _plan()
        self.analytics_report = _analytics_report()
        self.debate_history = _debate_history(self.plan)
        self.copy_specs = _copy_specs()
        self.visual_specs = _visual_specs()
        self.audio_specs = _audio_specs()
        self.video_specs = _video_specs()
        self.engagement_specs = _engagement_specs()
        self.pool = [{"row_number": 1, "quote": "Know thyself", "audience": "stuck"}]

        self.analytics_cls, self.analytics_instance = _tracked_class(
            "AnalyticsAnalystAgent", self.analytics_report, self.call_log)
        self.content_writer_cls, self.content_writer_instance = _tracked_class(
            "ContentWriterAgent", self.copy_specs, self.call_log)
        self.visual_designer_cls, self.visual_designer_instance = _tracked_class(
            "VisualDesignerAgent", self.visual_specs, self.call_log)
        self.audio_engineer_cls, self.audio_engineer_instance = _tracked_class(
            "AudioEngineerAgent", self.audio_specs, self.call_log)
        self.video_editor_cls, self.video_editor_instance = _tracked_class(
            "VideoEditorAgent", self.video_specs, self.call_log)
        self.engagement_cls, self.engagement_instance = _tracked_class(
            "EngagementStrategistAgent", self.engagement_specs, self.call_log)

        planner_instance = Mock(name="planner_instance")
        reviewer_instance = Mock(name="reviewer_instance")
        self.planner_cls = Mock(name="PlannerAgent", side_effect=lambda *a, **k: (
            self.call_log.append(("PlannerAgent.__init__", a, k)), planner_instance)[1])
        self.reviewer_cls = Mock(name="ReviewerAgent", side_effect=lambda *a, **k: (
            self.call_log.append(("ReviewerAgent.__init__", a, k)), reviewer_instance)[1])
        self.planner_instance = planner_instance
        self.reviewer_instance = reviewer_instance

        self.run_debate_mock = Mock(side_effect=lambda *a, **k: (
            self.call_log.append(("run_debate", a, k)),
            (self.plan, self.debate_history))[1])

        self.build_pool_mock = Mock(return_value=self.pool)
        self.init_db_mock = Mock()

    def apply(self, monkeypatch):
        monkeypatch.setattr(orchestrator, "AnalyticsAnalystAgent", self.analytics_cls)
        monkeypatch.setattr(orchestrator, "PlannerAgent", self.planner_cls)
        monkeypatch.setattr(orchestrator, "ReviewerAgent", self.reviewer_cls)
        monkeypatch.setattr(orchestrator, "run_debate", self.run_debate_mock)
        monkeypatch.setattr(orchestrator, "ContentWriterAgent", self.content_writer_cls)
        monkeypatch.setattr(orchestrator, "VisualDesignerAgent", self.visual_designer_cls)
        monkeypatch.setattr(orchestrator, "AudioEngineerAgent", self.audio_engineer_cls)
        monkeypatch.setattr(orchestrator, "VideoEditorAgent", self.video_editor_cls)
        monkeypatch.setattr(orchestrator, "EngagementStrategistAgent", self.engagement_cls)
        monkeypatch.setattr(orchestrator, "_build_pool", self.build_pool_mock)
        monkeypatch.setattr(orchestrator.data_store, "init_db", self.init_db_mock)
        monkeypatch.setattr(orchestrator, "_OUTPUT_DIR", self.tmp_path)


@pytest.fixture
def wired(monkeypatch, tmp_path):
    h = Harness(tmp_path)
    h.apply(monkeypatch)
    return h


# ── tests ────────────────────────────────────────────────────────────────────

def test_calls_agents_in_correct_dependency_order(wired):
    fake_client = Mock(name="fake_client")

    orchestrator.run_team_pipeline(client=fake_client)

    names = [entry[0] for entry in wired.call_log]
    assert names == [
        "AnalyticsAnalystAgent.__init__",
        "AnalyticsAnalystAgent.run",
        "PlannerAgent.__init__",
        "ReviewerAgent.__init__",
        "run_debate",
        "ContentWriterAgent.__init__",
        "ContentWriterAgent.run",
        "VisualDesignerAgent.__init__",
        "VisualDesignerAgent.run",
        "AudioEngineerAgent.__init__",
        "AudioEngineerAgent.run",
        "VideoEditorAgent.__init__",
        "VideoEditorAgent.run",
        "EngagementStrategistAgent.__init__",
        "EngagementStrategistAgent.run",
    ]

    # every Agent constructed with the injected client
    for cls in (wired.analytics_cls, wired.planner_cls, wired.reviewer_cls,
                wired.content_writer_cls, wired.visual_designer_cls,
                wired.audio_engineer_cls, wired.video_editor_cls, wired.engagement_cls):
        cls.assert_called_once_with(fake_client)

    # run_debate got the planner/reviewer instances + analytics report + pool
    debate_args = wired.run_debate_mock.call_args
    assert debate_args.args[0] is wired.planner_instance
    assert debate_args.args[1] is wired.reviewer_instance
    assert debate_args.args[2] is wired.analytics_report
    assert debate_args.args[3] is wired.pool

    # content_writer.run called with the plan run_debate produced
    wired.content_writer_instance.run.assert_called_once_with(wired.plan)

    # visual_designer / audio_engineer both got plan + copy_specs
    wired.visual_designer_instance.run.assert_called_once_with(wired.plan, wired.copy_specs)
    wired.audio_engineer_instance.run.assert_called_once_with(wired.plan, wired.copy_specs)

    # video_editor got plan + visual_specs + audio_specs (from earlier steps)
    wired.video_editor_instance.run.assert_called_once_with(
        wired.plan, wired.visual_specs, wired.audio_specs)

    # engagement got plan + copy_specs
    wired.engagement_instance.run.assert_called_once_with(wired.plan, wired.copy_specs)

    wired.init_db_mock.assert_called_once()
    wired.build_pool_mock.assert_called_once_with("quotes.xlsx")


def test_now_threaded_through_to_analytics_and_debate(wired):
    fake_client = Mock(name="fake_client")
    fixed_now = datetime(2026, 7, 9, 12, 0, 0)

    orchestrator.run_team_pipeline(client=fake_client, now=fixed_now)

    wired.analytics_instance.run.assert_called_once_with(now=fixed_now)
    debate_kwargs = wired.run_debate_mock.call_args.kwargs
    assert debate_kwargs.get("now") == fixed_now


def test_writes_all_seven_output_files_with_expected_shapes(wired, tmp_path):
    fake_client = Mock(name="fake_client")

    result = orchestrator.run_team_pipeline(client=fake_client)

    date = wired.plan.date
    expected_files = {
        "approved_plan": (f"approved_plan_{date}.json", wired.plan.to_dict()),
        "analytics_report": (f"analytics_report_{date}.json", wired.analytics_report.to_dict()),
        "copy": (f"copy_{date}.json", {"items": [c.to_dict() for c in wired.copy_specs]}),
        "visual_specs": (f"visual_specs_{date}.json",
                          {"items": [v.to_dict() for v in wired.visual_specs]}),
        "audio_specs": (f"audio_specs_{date}.json",
                         {"items": [a.to_dict() for a in wired.audio_specs]}),
        "video_specs": (f"video_specs_{date}.json",
                         {"items": [v.to_dict() for v in wired.video_specs]}),
        "engagement_specs": (f"engagement_specs_{date}.json",
                              {"items": [e.to_dict() for e in wired.engagement_specs]}),
    }

    assert set(result["output_paths"].keys()) == set(expected_files.keys())

    for key, (filename, expected_payload) in expected_files.items():
        path = result["output_paths"][key]
        assert path == tmp_path / filename
        assert path.exists()
        on_disk = json.loads(path.read_text())
        assert on_disk == expected_payload


def test_returned_dict_has_all_expected_keys(wired):
    fake_client = Mock(name="fake_client")

    result = orchestrator.run_team_pipeline(client=fake_client)

    assert result["analytics_report"] is wired.analytics_report
    assert result["approved_plan"] is wired.plan
    assert result["debate_history"] is wired.debate_history
    assert result["copy_specs"] is wired.copy_specs
    assert result["visual_specs"] is wired.visual_specs
    assert result["audio_specs"] is wired.audio_specs
    assert result["video_specs"] is wired.video_specs
    assert result["engagement_specs"] is wired.engagement_specs
    assert set(result["output_paths"].keys()) == {
        "approved_plan", "analytics_report", "copy", "visual_specs",
        "audio_specs", "video_specs", "engagement_specs",
    }


def test_client_none_builds_real_client_from_config(wired, monkeypatch):
    fake_cfg_instance = Mock(ANTHROPIC_API_KEY="fake-api-key")
    fake_cfg_cls = Mock(return_value=fake_cfg_instance)
    fake_studio_client_instance = Mock(name="fake_studio_client_instance")
    fake_studio_client_cls = Mock(return_value=fake_studio_client_instance)

    monkeypatch.setattr("config.Config", fake_cfg_cls)
    monkeypatch.setattr(orchestrator, "StudioClient", fake_studio_client_cls)

    result = orchestrator.run_team_pipeline(client=None)

    fake_cfg_cls.assert_called_once_with()
    fake_studio_client_cls.assert_called_once_with("fake-api-key")
    # the constructed client is what gets threaded to every agent
    wired.analytics_cls.assert_called_once_with(fake_studio_client_instance)
    assert result["approved_plan"] is wired.plan


def test_dry_run_false_returns_same_shape_and_does_not_touch_pipeline(wired):
    fake_client = Mock(name="fake_client")

    result = orchestrator.run_team_pipeline(dry_run=False, client=fake_client)

    assert set(result.keys()) == {
        "analytics_report", "approved_plan", "debate_history", "copy_specs",
        "visual_specs", "audio_specs", "video_specs", "engagement_specs",
        "output_paths",
    }


def test_orchestrator_module_never_imports_pipeline():
    """dry_run must not wire up real posting via pipeline.py in this task —
    enforced by checking the module never imports it (the word "pipeline" is
    fine in prose/identifiers like run_team_pipeline; an actual import isn't)."""
    import ast

    source = inspect.getsource(orchestrator)
    tree = ast.parse(source)
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module)

    assert not any(m == "pipeline" or m.startswith("pipeline.") for m in imported_modules)
    assert "import pipeline" not in source
