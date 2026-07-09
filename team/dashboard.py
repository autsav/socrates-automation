"""Flask + SSE live dashboard for the team pipeline.

`EventBus` is the single point of coordination: the pipeline thread (driven by
`team.live`) publishes events via the callbacks from `make_callbacks`, and any
number of browser tabs subscribe to `/events` and replay history + stream new
events. No external JS/CSS — the page is a single inline HTML document so it
works fully offline.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable

from flask import Flask, Response

PORT = 5001

# Stage keys must match the `name` values team.orchestrator.run_team_pipeline
# passes to on_stage_start/on_stage_done/on_stage_failed.
STAGES: list[tuple[str, str]] = [
    ("analytics", "Analytics"),
    ("debate", "Planner ↔ Reviewer Debate"),
    ("content_writer", "Content Writer"),
    ("visual_designer", "Visual Designer"),
    ("audio_engineer", "Audio Engineer"),
    ("video_editor", "Video Editor"),
    ("engagement_strategist", "Engagement Strategist"),
]


class EventBus:
    """Thread-safe pub/sub with history replay for late subscribers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: list[dict] = []
        self._subscribers: list[queue.Queue] = []

    def publish(self, event: dict) -> None:
        event = {**event, "ts": time.time()}
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)

    def subscribe(self) -> tuple[list[dict], "queue.Queue[dict]"]:
        q: "queue.Queue[dict]" = queue.Queue()
        with self._lock:
            history = list(self._history)
            self._subscribers.append(q)
        return history, q

    def unsubscribe(self, q: "queue.Queue[dict]") -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


def make_callbacks(bus: EventBus) -> dict[str, Callable]:
    """Build the on_* callback kwargs for team.orchestrator.run_team_pipeline."""

    def on_stage_start(stage: str) -> None:
        bus.publish({"type": "stage_start", "stage": stage})

    def on_stage_done(stage: str, summary: str) -> None:
        bus.publish({"type": "stage_done", "stage": stage, "summary": summary})

    def on_stage_failed(stage: str, error: str) -> None:
        bus.publish({"type": "stage_failed", "stage": stage, "error": error})

    def on_agent_activity(agent: str, activity: str) -> None:
        bus.publish({"type": "agent_activity", "agent": agent, "activity": activity})

    def on_debate_round(round_num: int, planner_output: str, reviewer_output: str,
                         score: float, approved: bool) -> None:
        bus.publish({
            "type": "debate_round",
            "round": round_num,
            "score": score,
            "approved": approved,
        })

    def on_log(level: str, message: str) -> None:
        bus.publish({"type": "log", "level": level, "message": message})

    def on_cost_update(cost_usd: float) -> None:
        bus.publish({"type": "cost_update", "cost_usd": cost_usd})

    def on_deliverable(agent: str, summary: str) -> None:
        bus.publish({"type": "deliverable", "agent": agent, "summary": summary})

    return {
        "on_stage_start": on_stage_start,
        "on_stage_done": on_stage_done,
        "on_stage_failed": on_stage_failed,
        "on_agent_activity": on_agent_activity,
        "on_debate_round": on_debate_round,
        "on_log": on_log,
        "on_cost_update": on_cost_update,
        "on_deliverable": on_deliverable,
    }


bus = EventBus()
app = Flask(__name__)


@app.route("/")
def index() -> str:
    return DASHBOARD_HTML.replace("__STAGES_JSON__", json.dumps(STAGES, ensure_ascii=False))


@app.route("/events")
def events() -> Response:
    history, q = bus.subscribe()

    def stream():
        try:
            for event in history:
                yield f"data: {json.dumps(event)}\n\n"
            while True:
                event = q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            bus.unsubscribe(q)

    return Response(stream(), mimetype="text/event-stream")


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Socrates Team — Live Pipeline</title>
<style>
  :root {
    --bg: #0a0a0f;
    --card: #14141f;
    --border: #24243a;
    --text: #e5e5ec;
    --muted: #8b8b9e;
    --green: #22c55e;
    --blue: #3b82f6;
    --gray: #6b7280;
    --red: #ef4444;
    --gradient: linear-gradient(90deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888);
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 24px;
  }
  .mono { font-family: "JetBrains Mono", "SF Mono", Menlo, monospace; }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding-bottom: 16px;
    margin-bottom: 20px;
    border-bottom: 2px solid transparent;
    border-image: var(--gradient) 1;
  }
  .header h1 {
    font-size: 20px;
    margin: 0;
  }
  .gradient-text {
    background: var(--gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .header-stats {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 14px;
    color: var(--muted);
  }
  .status-badge {
    padding: 4px 12px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.05em;
  }
  .status-running { background: rgba(59,130,246,0.15); color: var(--blue); }
  .status-done { background: rgba(34,197,94,0.15); color: var(--green); }
  .status-failed { background: rgba(239,68,68,0.15); color: var(--red); }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
  }
  .card h2 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 0 0 12px 0;
  }
  .main-grid {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 16px;
  }
  @media (max-width: 720px) {
    .main-grid { grid-template-columns: 1fr; }
  }
  #stages-list { list-style: none; margin: 0; padding: 0; }
  .stage {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 4px;
    font-size: 14px;
    transition: color 0.3s ease;
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--gray);
    flex-shrink: 0;
    transition: background 0.3s ease, box-shadow 0.3s ease;
  }
  .stage-running .dot { background: var(--blue); box-shadow: 0 0 8px var(--blue); }
  .stage-done .dot { background: var(--green); }
  .stage-failed .dot { background: var(--red); box-shadow: 0 0 8px var(--red); }
  .stage-done { color: var(--muted); }
  .stage-running { color: var(--text); font-weight: 600; }
  #activity-feed, #debate-feed, #deliverables-feed {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 220px;
    overflow-y: auto;
  }
  .activity-line, .debate-line, .deliverable-line {
    font-size: 13px;
    padding: 6px 10px;
    background: rgba(255,255,255,0.03);
    border-radius: 8px;
  }
  .agent-name { color: #e6683c; font-weight: 600; }
  .verdict-approved { color: var(--green); font-weight: 600; }
  .verdict-revise { color: #f09433; font-weight: 600; }
  #log-feed {
    max-height: 260px;
    overflow-y: auto;
    font-size: 12.5px;
    line-height: 1.6;
  }
  .log-line { white-space: pre-wrap; word-break: break-word; }
  .log-error { color: var(--red); }
  .log-info { color: var(--text); }
</style>
</head>
<body>

<div class="header">
  <h1><span class="gradient-text">SOCRATES TEAM</span> — LIVE PIPELINE</h1>
  <div class="header-stats">
    <span id="elapsed" class="mono">00:00:00</span>
    <span id="cost" class="mono">$0.0000</span>
    <span id="status" class="status-badge status-running">RUNNING</span>
  </div>
</div>

<div class="main-grid">
  <div class="card">
    <h2>Pipeline Stages</h2>
    <ul id="stages-list"></ul>
  </div>
  <div class="card">
    <h2>Agent Activity (live)</h2>
    <div id="activity-feed"></div>
  </div>
</div>

<div class="card">
  <h2>Debate</h2>
  <div id="debate-feed"></div>
</div>

<div class="card">
  <h2>Live Log</h2>
  <div id="log-feed" class="mono"></div>
</div>

<div class="card">
  <h2>Deliverables</h2>
  <div id="deliverables-feed"></div>
</div>

<script>
  const STAGES = __STAGES_JSON__;
  const stageStatus = {};
  STAGES.forEach(([key]) => { stageStatus[key] = "waiting"; });

  function renderStages() {
    const list = document.getElementById("stages-list");
    list.innerHTML = "";
    STAGES.forEach(([key, label]) => {
      const li = document.createElement("li");
      li.className = "stage stage-" + stageStatus[key];
      li.innerHTML = '<span class="dot"></span>' + label;
      list.appendChild(li);
    });
  }
  renderStages();

  let startTime = null;
  let done = false;

  function fmtElapsed(ms) {
    const s = Math.floor(ms / 1000);
    const hh = String(Math.floor(s / 3600)).padStart(2, "0");
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
    const ss = String(s % 60).padStart(2, "0");
    return hh + ":" + mm + ":" + ss;
  }

  setInterval(() => {
    if (startTime !== null && !done) {
      document.getElementById("elapsed").textContent = fmtElapsed(Date.now() - startTime);
    }
  }, 1000);

  function addLog(level, message, ts) {
    const feed = document.getElementById("log-feed");
    const line = document.createElement("div");
    line.className = "log-line log-" + level;
    const time = new Date(ts * 1000).toLocaleTimeString();
    line.textContent = "[" + time + "] " + message;
    feed.appendChild(line);
    feed.scrollTop = feed.scrollHeight;
  }

  function addActivity(agent, activity) {
    const feed = document.getElementById("activity-feed");
    const line = document.createElement("div");
    line.className = "activity-line";
    line.innerHTML = "<span class=\\"agent-name\\">" + agent + "</span> " + activity;
    feed.prepend(line);
  }

  function addDebateRound(round, score, approved) {
    const feed = document.getElementById("debate-feed");
    const line = document.createElement("div");
    line.className = "debate-line";
    const verdict = approved
      ? '<span class="verdict-approved">APPROVED &#10003;</span>'
      : '<span class="verdict-revise">REVISE</span>';
    line.innerHTML = "Round " + round + ": Planner &#8594; Reviewer — score " +
      score.toFixed(1) + "/10 — " + verdict;
    feed.appendChild(line);
  }

  function addDeliverable(agent, summary) {
    const feed = document.getElementById("deliverables-feed");
    const line = document.createElement("div");
    line.className = "deliverable-line";
    line.innerHTML = "<span class=\\"agent-name\\">" + agent + "</span>: " + summary;
    feed.appendChild(line);
  }

  function setStatus(text, cls) {
    const el = document.getElementById("status");
    el.textContent = text;
    el.className = "status-badge status-" + cls;
  }

  const es = new EventSource("/events");
  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (startTime === null) startTime = ev.ts * 1000;

    switch (ev.type) {
      case "stage_start":
        stageStatus[ev.stage] = "running";
        renderStages();
        break;
      case "stage_done":
        stageStatus[ev.stage] = "done";
        renderStages();
        addLog("info", ev.stage + ": " + ev.summary, ev.ts);
        break;
      case "stage_failed":
        stageStatus[ev.stage] = "failed";
        renderStages();
        setStatus("FAILED", "failed");
        addLog("error", ev.stage + " FAILED: " + ev.error, ev.ts);
        break;
      case "agent_activity":
        addActivity(ev.agent, ev.activity);
        addLog("info", ev.agent + ": " + ev.activity, ev.ts);
        break;
      case "debate_round":
        addDebateRound(ev.round, ev.score, ev.approved);
        break;
      case "log":
        addLog(ev.level, ev.message, ev.ts);
        break;
      case "cost_update":
        document.getElementById("cost").textContent = "$" + ev.cost_usd.toFixed(4);
        break;
      case "deliverable":
        addDeliverable(ev.agent, ev.summary);
        break;
      case "pipeline_complete":
        done = true;
        setStatus("COMPLETE", "done");
        addLog("info", "PIPELINE COMPLETE — " + ev.summary, ev.ts);
        break;
      case "pipeline_failed":
        done = true;
        setStatus("FAILED", "failed");
        addLog("error", "PIPELINE FAILED — " + ev.error, ev.ts);
        break;
    }
  };
</script>
</body>
</html>
"""
