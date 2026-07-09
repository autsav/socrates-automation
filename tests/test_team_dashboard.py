import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import team.dashboard as dashboard
import team.orchestrator as orchestrator
from team.dashboard import EventBus, make_callbacks
from team.models import (
    AnalyticsReport, ContentPlan, PostPlan, DebateResult, TrendReport,
    CopySpec, VisualSpec, AudioSpec, VideoSpec, VideoQualityScore, EngagementSpec,
)


# ── EventBus ─────────────────────────────────────────────────────────────────

def test_publish_adds_ts_and_appends_to_history():
    bus = EventBus()
    bus.publish({"type": "log", "level": "info", "message": "hi"})

    assert len(bus._history) == 1
    event = bus._history[0]
    assert event["type"] == "log"
    assert event["message"] == "hi"
    assert isinstance(event["ts"], float)


def test_subscribe_replays_existing_history_then_receives_new_events():
    bus = EventBus()
    bus.publish({"type": "log", "level": "info", "message": "before"})

    history, q = bus.subscribe()
    assert len(history) == 1
    assert history[0]["message"] == "before"

    bus.publish({"type": "log", "level": "info", "message": "after"})
    delivered = q.get_nowait()
    assert delivered["message"] == "after"


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    _, q = bus.subscribe()
    bus.unsubscribe(q)

    bus.publish({"type": "log", "level": "info", "message": "missed"})
    assert q.empty()


def test_multiple_subscribers_each_get_their_own_queue():
    bus = EventBus()
    _, q1 = bus.subscribe()
    _, q2 = bus.subscribe()

    bus.publish({"type": "log", "level": "info", "message": "fanout"})

    assert q1.get_nowait()["message"] == "fanout"
    assert q2.get_nowait()["message"] == "fanout"


# ── make_callbacks ───────────────────────────────────────────────────────────

def test_make_callbacks_returns_all_eight_hooks():
    bus = EventBus()
    callbacks = make_callbacks(bus)

    assert set(callbacks.keys()) == {
        "on_stage_start", "on_stage_done", "on_stage_failed", "on_agent_activity",
        "on_debate_round", "on_log", "on_cost_update", "on_deliverable",
    }


def test_each_callback_publishes_the_expected_event_shape():
    bus = EventBus()
    callbacks = make_callbacks(bus)

    callbacks["on_stage_start"]("analytics")
    callbacks["on_stage_done"]("analytics", "10 posts analyzed")
    callbacks["on_stage_failed"]("debate", "boom")
    callbacks["on_agent_activity"]("Planner", "drafting plan")
    callbacks["on_debate_round"](1, "{}", "{}", 8.5, True)
    callbacks["on_log"]("info", "starting")
    callbacks["on_cost_update"](0.42)
    callbacks["on_deliverable"]("Content Writer", "copy for 7 posts")

    events = bus._history
    assert events[0] == {"type": "stage_start", "stage": "analytics", "ts": events[0]["ts"]}
    assert events[1] == {"type": "stage_done", "stage": "analytics",
                          "summary": "10 posts analyzed", "ts": events[1]["ts"]}
    assert events[2] == {"type": "stage_failed", "stage": "debate",
                          "error": "boom", "ts": events[2]["ts"]}
    assert events[3] == {"type": "agent_activity", "agent": "Planner",
                          "activity": "drafting plan", "ts": events[3]["ts"]}
    assert events[4] == {"type": "debate_round", "round": 1, "score": 8.5,
                          "approved": True, "ts": events[4]["ts"]}
    assert events[5] == {"type": "log", "level": "info", "message": "starting",
                          "ts": events[5]["ts"]}
    assert events[6] == {"type": "cost_update", "cost_usd": 0.42, "ts": events[6]["ts"]}
    assert events[7] == {"type": "deliverable", "agent": "Content Writer",
                          "summary": "copy for 7 posts", "ts": events[7]["ts"]}


# ── Flask app ────────────────────────────────────────────────────────────────

def test_index_serves_html_with_stage_labels_and_no_leftover_placeholder():
    client = dashboard.app.test_client()

    resp = client.get("/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "__STAGES_JSON__" not in body
    for key, label in dashboard.STAGES:
        assert label in body
        assert key in body


def test_events_route_replays_history_as_sse_then_streams_new_events():
    bus = EventBus()
    dashboard.bus = bus
    bus.publish({"type": "log", "level": "info", "message": "replayed"})

    with dashboard.app.test_request_context():
        response = dashboard.events()
        chunks = response.response  # the generator passed to Response()

        first = next(chunks)
        assert first.startswith("data: ")
        payload = json.loads(first[len("data: "):].strip())
        assert payload["message"] == "replayed"

        bus.publish({"type": "log", "level": "info", "message": "live"})
        second = next(chunks)
        payload2 = json.loads(second[len("data: "):].strip())
        assert payload2["message"] == "live"


# ── orchestrator + dashboard integration ─────────────────────────────────────

def _analytics_report():
    return AnalyticsReport(
        date="2026-07-09", total_posts=10, avg_engagement_rate=0.05,
        top_performing_hooks=["hook_a"], top_performing_moods=["dark_philosophical"],
        best_posting_times=["07:00"], worst_performing_content=["hook_z"],
        recommendations=["Post more at 07:00"], follower_growth=100, save_rate=0.02,
    )


def _post(n):
    return PostPlan(
        post_number=n, posting_time="07:00", quote_id=n, audience="stuck",
        mood="dark_philosophical", format="reel", hook_strategy="contrarian",
        visual_style="cinematic", audio_strategy="lofi build",
        engagement_strategy="seed comment", controversy_question="Is discipline overrated?",
        cta="save this", hashtags=["#stoic"], estimated_viral_potential=7.5,
        rationale="ties to top_performing_hooks",
    )


def _plan(date="2026-07-09"):
    return ContentPlan(date=date, posts=[_post(n) for n in range(1, 8)])


def _specs_of(cls, n=7, **extra):
    return [cls(post_number=i, **extra) for i in range(1, n + 1)]


@pytest.fixture
def wired_pipeline(monkeypatch, tmp_path):
    plan = _plan()
    analytics_report = _analytics_report()
    debate_history = [DebateResult(
        round_number=1, planner_output=json.dumps(plan.to_dict()),
        reviewer_output=json.dumps({"score": 9.0}), reviewer_score=9.0,
        approved=True, final_plan=plan,
    )]
    copy_specs = _specs_of(CopySpec, hook="h", caption="c", cta="cta",
                           controversy_question="q", hashtags=["#a"],
                           carousel_slides=["s"], story_teaser="t")
    visual_specs = _specs_of(VisualSpec, flux_prompt="p", composition_params={},
                             wallpaper_design={}, carousel_design=[{}],
                             color_palette={}, font_choice={})
    audio_specs = _specs_of(AudioSpec, music_track="m", voiceover_text="v",
                            voiceover_emotion="calm", beat_markers=[1.0],
                            mix_levels={}, jingle=False)
    video_specs = _specs_of(VideoSpec, scenes=[{}], total_duration=30.0,
                            transitions=["cut"], motion_effects=["kb"],
                            text_overlays=[{}], aspect_ratio="9:16")
    trend_report = TrendReport(
        niche="", hashtags=[{"name": "fyp", "views": 0, "posts": 0, "trend": 1}],
        sounds=[], fetched_at="2026-07-09T00:00:00+00:00",
    )
    video_quality_scores = _specs_of(VideoQualityScore, visual_appeal=8,
                                     text_readability=8, content_relevance=8,
                                     production_quality=8, overall_score=8.0,
                                     is_acceptable=True, feedback="solid",
                                     suggestions="none")
    engagement_specs = _specs_of(EngagementSpec, seed_comments=["c"],
                                 reply_templates=["r"], dm_trigger="d",
                                 save_bait_frame="f", story_teaser="t",
                                 highlight_category="cat")

    def _agent(return_value):
        instance = Mock()
        instance.run = Mock(return_value=return_value)
        return Mock(return_value=instance)

    monkeypatch.setattr(orchestrator, "AnalyticsAnalystAgent", _agent(analytics_report))
    trend_scraper_cls = Mock(return_value=Mock(run=Mock(return_value=trend_report)))
    monkeypatch.setattr(orchestrator, "TrendScraperAgent", trend_scraper_cls)
    monkeypatch.setattr(orchestrator, "PlannerAgent", Mock(return_value=Mock()))
    monkeypatch.setattr(orchestrator, "ReviewerAgent", Mock(return_value=Mock()))

    def _fake_run_debate(*args, **kwargs):
        on_round = kwargs.get("on_round")
        if on_round is not None:
            on_round(1, json.dumps(plan.to_dict()), json.dumps({"score": 9.0}), 9.0, True)
        return plan, debate_history

    monkeypatch.setattr(orchestrator, "run_debate", Mock(side_effect=_fake_run_debate))
    monkeypatch.setattr(orchestrator, "ContentWriterAgent", _agent(copy_specs))
    monkeypatch.setattr(orchestrator, "VisualDesignerAgent", _agent(visual_specs))
    monkeypatch.setattr(orchestrator, "AudioEngineerAgent", _agent(audio_specs))
    monkeypatch.setattr(orchestrator, "VideoEditorAgent", _agent(video_specs))
    video_quality_cls = _agent(video_quality_scores)
    video_quality_cls.needs_regeneration = Mock(return_value=[])
    monkeypatch.setattr(orchestrator, "VideoQualityReviewerAgent", video_quality_cls)
    monkeypatch.setattr(orchestrator, "EngagementStrategistAgent", _agent(engagement_specs))
    monkeypatch.setattr(orchestrator, "_build_pool", Mock(return_value=[]))
    monkeypatch.setattr(orchestrator.data_store, "init_db", Mock())
    monkeypatch.setattr(orchestrator, "_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(orchestrator, "_current_spend_usd", Mock(return_value=0.1234))


def test_run_team_pipeline_drives_dashboard_events_end_to_end(wired_pipeline):
    bus = EventBus()
    callbacks = make_callbacks(bus)

    orchestrator.run_team_pipeline(client=Mock(), **callbacks)

    types = [e["type"] for e in bus._history]
    stages_started = [e["stage"] for e in bus._history if e["type"] == "stage_start"]
    stages_done = [e["stage"] for e in bus._history if e["type"] == "stage_done"]

    assert stages_started == [
        "analytics", "trend_scraper", "debate", "content_writer", "visual_designer",
        "audio_engineer", "video_editor", "video_quality_reviewer", "engagement_strategist",
    ]
    assert stages_done == stages_started
    assert types.count("deliverable") == 9
    assert types.count("cost_update") == 9
    assert any(e["type"] == "debate_round" and e["round"] == 1 and e["approved"] is True
               for e in bus._history)
    assert any(e["type"] == "log" and e["message"] == "Pipeline complete"
               for e in bus._history)


def test_stage_failure_publishes_stage_failed_and_reraises(wired_pipeline):
    bus = EventBus()
    callbacks = make_callbacks(bus)
    boom = RuntimeError("agent exploded")
    orchestrator.AnalyticsAnalystAgent.return_value.run.side_effect = boom

    with pytest.raises(RuntimeError, match="agent exploded"):
        orchestrator.run_team_pipeline(client=Mock(), **callbacks)

    failed = [e for e in bus._history if e["type"] == "stage_failed"]
    assert len(failed) == 1
    assert failed[0]["stage"] == "analytics"
    assert failed[0]["error"] == "agent exploded"
    # no stage_done should have fired for the failed stage
    assert not any(e["type"] == "stage_done" for e in bus._history)
