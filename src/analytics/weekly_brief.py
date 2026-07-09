"""
Weekly Performance Brief Generator

Auto-generates a weekly performance report every Monday.
Uses historical data from SQLite to identify:
- Top 3 performing posts
- Bottom 3 posts (learning opportunities)
- Cohort winners (best slot, mood, audience)
- Hook leaderboard
- Funnel bottlenecks
- Action items for the week ahead

Output: Markdown brief sent via Telegram or saved to file.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from src.analytics.cohort_analysis import (
    get_optimal_posting_window,
    get_day_of_week_breakdown,
    get_top_performing_posts,
    get_bottom_performing_posts,
    aggregate_funnel_averages,
    statistical_significance,
)
from src.analytics.hook_tracker import get_hook_leaderboard
from src.video.predictive_scoring import get_prediction_accuracy


def generate_weekly_brief(window_days: int = 7) -> str:
    """
    Generate a complete weekly performance brief as Markdown.
    """
    now = datetime.utcnow()
    week_start = now - timedelta(days=window_days)

    lines = [
        f"# 📊 Socrates Pipeline — Weekly Performance Brief",
        f"",
        f"**Period:** {week_start.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        "---",
        "",
    ]

    # ── Section 1: Top Performers ────────────────────────────────────────────
    lines.append("## 🏆 Top Performers")
    lines.append("")
    top_posts = get_top_performing_posts(n=3, window_days=window_days)
    if top_posts:
        for i, post in enumerate(top_posts, 1):
            lines.append(f"**{i}. Score {post['composite_score']}** | {post['mood']} | {post['audience']}")
            lines.append(f"   \"{post['quote_text']}\"")
            lines.append(f"   💾 {post['saved']} saves | 💬 {post['comments']} comments | 👁 {post['reach']} reach")
            lines.append("")
    else:
        lines.append("*No posts with metrics yet this week.*")
        lines.append("")

    # ── Section 2: Learning Opportunities ─────────────────────────────────────
    lines.append("## 📉 Learning Opportunities (Bottom 3)")
    lines.append("")
    bottom_posts = get_bottom_performing_posts(n=3, window_days=window_days)
    if bottom_posts:
        for i, post in enumerate(bottom_posts, 1):
            lines.append(f"**{i}. Score {post['composite_score']}** | {post['mood']} | {post['audience']}")
            lines.append(f"   \"{post['quote_text']}\"")
            lines.append(f"   💾 {post['saved']} | 💬 {post['comments']} | 👁 {post['reach']}")
            lines.append("")
    else:
        lines.append("*No data available.*")
        lines.append("")

    # ── Section 3: Cohort Insights ───────────────────────────────────────────
    lines.append("## 📊 Cohort Insights")
    lines.append("")

    # Best posting slot
    slot_data = get_optimal_posting_window(window_days=max(window_days, 30))
    if slot_data.get("status") == "ok":
        lines.append(f"**🕐 Best Posting Slot:** {slot_data['slot_name']} ({slot_data['avg_engagement_rate']}% engagement, {slot_data['n_posts']} posts)")
        lines.append(f"   Confidence: {slot_data['confidence']}")
    else:
        lines.append(f"**🕐 Best Posting Slot:** *{slot_data.get('message', 'No data')}*")
    lines.append("")

    # Day of week
    day_breakdown = get_day_of_week_breakdown(window_days=max(window_days, 30))
    if day_breakdown:
        best_day = max(day_breakdown, key=lambda x: x.get("engagement_rate", 0))
        lines.append(f"**📅 Best Day:** {best_day['day_name']} ({best_day['engagement_rate']}% engagement)")
        lines.append("")

    # ── Section 4: Hook Leaderboard ──────────────────────────────────────────
    lines.append("## 🪝 Hook Leaderboard")
    lines.append("")
    leaderboard = get_hook_leaderboard(window_days=max(window_days, 30), min_trials=2)
    if leaderboard["top_overall"]:
        lines.append("**Top Hooks (by composite score):**")
        for i, hook in enumerate(leaderboard["top_overall"][:3], 1):
            lines.append(f"{i}. `{hook['hook_id']}` — {hook['composite_score']} pts ({hook['n']} trials)")
            lines.append(f"   _{hook['template'][:70]}..._")
        lines.append("")
        if leaderboard["needs_more_data"]:
            lines.append(f"**Needs more data:** {', '.join(leaderboard['needs_more_data'][:5])}")
            lines.append("")
    else:
        lines.append("*Not enough hook data yet. Keep posting!*")
        lines.append("")

    # ── Section 5: Funnel Analysis ───────────────────────────────────────────
    lines.append("## 🔄 Funnel Analysis")
    lines.append("")
    funnel = aggregate_funnel_averages(window_days=window_days)
    if funnel.get("status") != "insufficient_data":
        impressions = funnel.get("avg_impressions", 0)
        reach = funnel.get("avg_reach", 0)
        views = funnel.get("avg_views", 0)
        hold_3s = funnel.get("avg_hold_3s", 0)
        completions = funnel.get("avg_completions", 0)
        saves = funnel.get("avg_saves", 0)

        lines.append(f"```")
        lines.append(f"Impressions  →  Reach:       {impressions:>8.0f} → {reach:>8.0f} ({reach/max(impressions,1)*100:.1f}%)")
        lines.append(f"Reach      →  Views:         {reach:>8.0f} → {views:>8.0f} ({views/max(reach,1)*100:.1f}%)")
        lines.append(f"Views      →  3s Hold:       {views:>8.0f} → {hold_3s:>8.0f} ({hold_3s/max(views,1)*100:.1f}%)")
        lines.append(f"3s Hold    →  Completion:    {hold_3s:>8.0f} → {completions:>8.0f} ({completions/max(hold_3s,1)*100:.1f}%)")
        lines.append(f"Completion →  Save:          {completions:>8.0f} → {saves:>8.0f} ({saves/max(completions,1)*100:.1f}%)")
        lines.append(f"```")
        lines.append("")

        # Identify bottleneck
        rates = [
            ("Reach rate", reach / max(impressions, 1)),
            ("View rate", views / max(reach, 1)),
            ("3s hold rate", hold_3s / max(views, 1)),
            ("Completion rate", completions / max(hold_3s, 1)),
            ("Save rate", saves / max(completions, 1)),
        ]
        bottleneck_name, bottleneck_rate = min(rates, key=lambda x: x[1])
        lines.append(f"⚠️ **Biggest bottleneck:** {bottleneck_name} ({bottleneck_rate*100:.1f}%)")
        lines.append("")
    else:
        lines.append("*Not enough funnel data yet.*")
        lines.append("")

    # ── Section 6: Prediction Accuracy ───────────────────────────────────────
    lines.append("## 🔮 Prediction Accuracy")
    lines.append("")
    pred_acc = get_prediction_accuracy(window_days=max(window_days, 30))
    if pred_acc.get("status") != "insufficient_data":
        lines.append(f"- **MAE:** {pred_acc['mae']:.1f} points")
        lines.append(f"- **Correlation:** {pred_acc['correlation']:.3f}")
        lines.append(f"- **Predicted vs Actual:** {pred_acc['mean_predicted']:.1f} vs {pred_acc['mean_actual']:.1f}")
        lines.append(f"- **Sample size:** {pred_acc['n']} posts")
        lines.append("")
    else:
        lines.append(f"*{pred_acc.get('message', 'No predictions to evaluate yet')}*")
        lines.append("")

    # ── Section 7: Action Items ──────────────────────────────────────────────
    lines.append("## ✅ Action Items for This Week")
    lines.append("")
    actions = _generate_action_items(
        top_posts,
        bottom_posts,
        slot_data,
        leaderboard,
        funnel if funnel.get("status") != "insufficient_data" else None,
    )
    for i, action in enumerate(actions, 1):
        lines.append(f"{i}. {action}")
    lines.append("")

    # ── Section 8: A/B Test Recommendations ──────────────────────────────────
    lines.append("## 🧪 A/B Test Recommendations")
    lines.append("")
    tests = _generate_ab_recommendations(window_days)
    for test in tests:
        lines.append(f"- {test}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Generated by Socrates Analytics Engine v4.0*")
    lines.append("*Next brief: next Monday*")

    return "\n".join(lines)


def _generate_action_items(top_posts, bottom_posts, slot_data, leaderboard, funnel) -> list[str]:
    """Generate actionable recommendations based on data."""
    actions = []

    # Slot optimization
    if slot_data and slot_data.get("status") == "ok":
        actions.append(f"Double down on **{slot_data['slot_name']}** posts — they show {slot_data['avg_engagement_rate']}% engagement")

    # Hook doubling
    if leaderboard and leaderboard.get("top_overall"):
        top_hook = leaderboard["top_overall"][0]
        actions.append(f"Use more **{top_hook['category']}** hooks — `{top_hook['hook_id']}` leads at {top_hook['composite_score']} pts")

    # Avoid underperformers
    if bottom_posts:
        worst_mood = bottom_posts[0]["mood"]
        worst_aud = bottom_posts[0]["audience"]
        actions.append(f"Avoid **{worst_mood}** mood + **{worst_aud}** audience combo this week")

    # Funnel fixes
    if funnel:
        impressions = funnel.get("avg_impressions", 0)
        reach = funnel.get("avg_reach", 0)
        views = funnel.get("avg_views", 0)
        hold_3s = funnel.get("avg_hold_3s", 0)
        completions = funnel.get("avg_completions", 0)
        saves = funnel.get("avg_saves", 0)

        rates = [
            ("Reach rate", reach / max(impressions, 1), "Distribution"),
            ("View rate", views / max(reach, 1), "Thumbnail/Hook"),
            ("3s hold rate", hold_3s / max(views, 1), "Opening hook"),
            ("Completion rate", completions / max(hold_3s, 1), "Content retention"),
            ("Save rate", saves / max(completions, 1), "CTA/Save-bait design"),
        ]
        bottleneck_name, bottleneck_rate, fix_area = min(rates, key=lambda x: x[1])
        if bottleneck_rate < 0.3:
            actions.append(f"Fix **{fix_area}** — {bottleneck_name} is only {bottleneck_rate*100:.1f}% (biggest drop-off)")

    # Content doubling
    if top_posts:
        top_mood = top_posts[0]["mood"]
        top_aud = top_posts[0]["audience"]
        actions.append(f"Create 2 more **{top_mood}** mood + **{top_aud}** audience posts this week")

    # Default if empty
    if not actions:
        actions = [
            "Post consistently — need more data for actionable insights",
            "Ensure all posts have metrics fetched (check analytics cron)",
            "Test 2 new hook templates this week",
        ]

    return actions


def _generate_ab_recommendations(window_days: int) -> list[str]:
    """Suggest A/B tests based on data gaps."""
    recommendations = []

    # Check for under-tested dimensions
    from src.analytics.cohort_analysis import compare_cohorts

    moods = ["dark_philosophical", "epic_warrior", "calm_stoic", "mystical_greek", "cinematic_hopeful", "stark_minimal", "dramatic_ancient"]
    mood_results = compare_cohorts("mood", moods, window_days)
    tested_moods = [r["value"] for r in mood_results if r.get("n", 0) > 0]
    untested = set(moods) - set(tested_moods)
    if untested:
        recommendations.append(f"Test untested moods: {', '.join(list(untested)[:3])}")

    slots = ["0", "1", "2"]
    slot_results = compare_cohorts("posting_slot", slots, window_days)
    tested_slots = [r["value"] for r in slot_results if r.get("n", 0) > 0]
    untested_slots = set(slots) - set(tested_slots)
    if untested_slots:
        recommendations.append(f"Test untested posting slots: {', '.join(untested_slots)}")

    if not recommendations:
        recommendations = [
            "Test hook type: pattern_interrupt vs question",
            "Test mood: epic_warrior vs dark_philosophical",
            "Test CTA placement: middle vs end of caption",
        ]

    return recommendations


def save_brief(brief_md: str, output_dir: Path | str = "briefs") -> Path:
    """Save the brief to a file and return the path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    filename = f"weekly_brief_{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    path = out / filename
    path.write_text(brief_md, encoding="utf-8")
    return path


def get_latest_brief_path(output_dir: Path | str = "briefs") -> Path | None:
    """Return the most recent brief file."""
    out = Path(output_dir)
    if not out.exists():
        return None
    files = sorted(out.glob("weekly_brief_*.md"), reverse=True)
    return files[0] if files else None
