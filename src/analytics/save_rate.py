"""
Point 44: Save Rate as Primary KPI.

Saves are weighted highest by the Instagram algorithm:
  saves > likes > comments (for reach amplification)

Adds save_rate column to all analytics queries and surfaces
a ranked report sorted by save_rate desc.
"""


def calculate_save_rate(saved: int, reach: int) -> float:
    """
    save_rate = saves / reach.
    Returns 0.0 if reach is zero.
    Benchmark: >5% = S-tier, 2-5% = A-tier, <2% = B-tier.
    """
    if reach <= 0:
        return 0.0
    return saved / reach


def get_save_rate_report(limit: int = 20) -> list[dict]:
    """
    Point 44: Pull save rate as primary KPI for all tracked posts.
    Returns list of dicts sorted by save_rate desc.
    """
    try:
        from src.core.data_store import _get_connection
    except ImportError:
        print("  [analytics] data_store not available")
        return []

    conn = _get_connection()
    try:
        conn.row_factory = __import__("sqlite3").Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                p.post_id,
                p.quote_text,
                p.mood,
                p.posted_at,
                m.saved,
                m.reach,
                m.likes,
                m.comments,
                m.impressions,
                CASE WHEN m.reach > 0 THEN CAST(m.saved AS REAL) / m.reach ELSE 0 END AS save_rate
            FROM posts p
            JOIN post_metrics m ON p.post_id = m.post_id
            ORDER BY save_rate DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    report = []
    for row in rows:
        sr = calculate_save_rate(row["saved"], row["reach"])
        report.append({
            "post_id": row["post_id"],
            "quote_text": (row["quote_text"] or "")[:60],
            "mood": row["mood"],
            "posted_at": row["posted_at"],
            "saved": row["saved"],
            "reach": row["reach"],
            "likes": row["likes"],
            "comments": row["comments"],
            "save_rate": round(sr * 100, 2),        # as percentage
            "save_rate_rank": "S" if sr >= 0.05 else ("A" if sr >= 0.02 else "B"),
        })
    return report


def print_save_rate_report(report: list[dict]) -> None:
    """Print save rate KPI table to stdout."""
    if not report:
        print("  [analytics] No posts with metrics yet.")
        return
    print(f"\n{'Post ID':<20} {'Save%':>6} {'Rank':>4}  {'Saved':>5} {'Reach':>6}  Quote")
    print("-" * 90)
    for row in report:
        print(
            f"{row['post_id']:<20} {row['save_rate']:>5.2f}%  {row['save_rate_rank']:>4}"
            f"  {row['saved']:>5} {row['reach']:>6}  {row['quote_text']}"
        )
