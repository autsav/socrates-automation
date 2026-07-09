"""
Analytics Ingestion — fetch Meta Insights metrics ~24h after posting.
Runs as a separate cron job (GitHub Actions analytics.yml).
"""

import requests

GRAPH_URL = "https://graph.instagram.com/v22.0"

METRICS = ["likes", "comments", "shares", "reach", "impressions", "saved"]


def fetch_post_metrics(
    post_id: str,
    access_token: str,
    ig_account_id: str,
) -> dict:
    """
    Fetch insights for a single post from Meta Insights API.
    Returns dict with all metric names (default 0 if missing).
    """
    url = f"{GRAPH_URL}/{post_id}/insights"
    params = {
        "metric": ",".join(METRICS),
        "access_token": access_token,
    }

    response = requests.get(url, params=params, timeout=15)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        # Sanitize URL to prevent access_token leak in logs
        safe_url = response.url.replace(access_token, "<REDACTED>")
        raise requests.HTTPError(
            f"{exc.response.status_code} for {safe_url}",
            response=exc.response,
        ) from exc
    data = response.json()

    result = {m: 0 for m in METRICS}
    for item in data.get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        if name in result and values:
            result[name] = values[0].get("value", 0)

    return result


def ingest_all_pending(
    access_token: str,
    ig_account_id: str,
    dry_run: bool = False,
) -> int:
    """
    Find all posts older than 24h with no metrics, fetch and store.
    Returns count of posts updated.
    """
    try:
        from src.core.data_store import _get_connection
    except ImportError:
        print("  [analytics] data_store not available, skipping")
        return 0

    conn = _get_connection()
    try:
        conn.row_factory = __import__("sqlite3").Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT p.post_id
            FROM posts p
            LEFT JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.post_id IS NOT NULL
              AND p.posted_at IS NOT NULL
              AND p.posted_at <= datetime('now', '-1 day')
              AND m.post_id IS NULL
            """
        )
        pending = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    if not pending:
        print("  [analytics] No pending posts to ingest")
        return 0

    print(f"  [analytics] Fetching metrics for {len(pending)} post(s)...")
    updated = 0

    for post_id in pending:
        if dry_run:
            print(f"    [dry-run] Would fetch metrics for {post_id}")
            updated += 1
            continue

        try:
            metrics = fetch_post_metrics(post_id, access_token, ig_account_id)
            conn = _get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO post_metrics (post_id, likes, comments, shares, reach, impressions, saved)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post_id,
                        metrics.get("likes", 0),
                        metrics.get("comments", 0),
                        metrics.get("shares", 0),
                        metrics.get("reach", 0),
                        metrics.get("impressions", 0),
                        metrics.get("saved", 0),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            updated += 1
            print(f"    [analytics] Ingested metrics for {post_id}")
        except Exception as e:
            print(f"    [analytics] Failed to fetch metrics for {post_id}: {e}")

    print(f"  [analytics] Updated {updated}/{len(pending)} posts")
    return updated


def calculate_save_rate(saved: int, reach: int) -> float:
    """
    Point 44: Save rate = saves / reach.
    Saves outrank likes and comments for the algorithm.
    Returns 0.0 if reach is zero.
    """
    if reach <= 0:
        return 0.0
    return saved / reach


def get_save_rate_report(
    access_token: str,
    ig_account_id: str,
    limit: int = 20,
) -> list[dict]:
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


if __name__ == "__main__":
    import argparse
    from config import Config

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Log what would be done without fetching")
    args = parser.parse_args()

    cfg = Config()
    count = ingest_all_pending(cfg.META_ACCESS_TOKEN, cfg.IG_ACCOUNT_ID, dry_run=args.dry_run)
    print(f"Done. Ingested {count} posts.")
