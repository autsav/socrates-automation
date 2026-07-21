"""Per-agent performance digests over posts x post_metrics (spec 2.2).
sends-per-reach is the north star; reach floor kills small-sample noise.

Schema note (VERIFIED against src/core/data_store.py:60-76, init_db): the real
`posts` table has an `arc` column but NO `hook` or `caption` column. Hook
text lives only in the in-code HOOK_TEMPLATES dict (src/analytics/
hook_tracker.py) keyed by posts.hook_id — not queryable via SQL join.
Caption text is never persisted to sqlite at all (only transient in-memory /
data/approvals.json). The only always-populated (NOT NULL), human-readable
column is `quote_text`, so it stands in as the hook surrogate here — first
line only, in case a quote spans multiple lines.
"""
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent.parent / "data" / "pipeline.db"
CACHE = DEFAULT_DB.parent / "perf_digest.json"
REACH_FLOOR = 100
TOP_N = 3


def _hook_surrogate(quote_text) -> str:
    """First line of quote_text, stripped. quote_text is the only reliably
    populated human-readable field on `posts` (see module docstring)."""
    if not quote_text:
        return ""
    return quote_text.strip().splitlines()[0].strip()


def _rows(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        return con.execute(
            "SELECT p.arc, p.quote_text, m.shares, m.reach FROM posts p "
            "JOIN post_metrics m ON p.post_id = m.post_id "
            "WHERE p.dry_run=0 AND m.reach >= ?", (REACH_FLOOR,)).fetchall()
    finally:
        con.close()


def build_digest(db_path=DEFAULT_DB) -> dict:
    try:
        scored = sorted(
            ({"arc": arc or "?", "hook": _hook_surrogate(quote_text),
              "sends_per_reach": round(shares / reach, 4)}
             for arc, quote_text, shares, reach in _rows(db_path) if reach),
            key=lambda e: e["sends_per_reach"], reverse=True)
        if not scored:
            return {}
        top = [dict(e, rank="top") for e in scored[:TOP_N]]
        bottom = [dict(e, rank="bottom") for e in scored[-TOP_N:]
                  if e not in scored[:TOP_N]]
        view = top + bottom
        digest = {"story_writer": view, "copywriter": view, "strategist": view}
        try:
            CACHE.write_text(json.dumps(digest, indent=2))
        except Exception:  # noqa: BLE001 - cache is best-effort
            pass
        return digest
    except Exception:  # noqa: BLE001 - digest must never break generation
        return {}


def winning_scripts(n=2, db_path=DEFAULT_DB) -> list[dict]:
    """Top real scripts by sends-per-reach (spec 5). [] until >=3 scored."""
    import json as _json
    try:
        con = sqlite3.connect(str(db_path))
        try:
            rows = con.execute(
                "SELECT p.script_json, m.shares, m.reach FROM posts p "
                "JOIN post_metrics m ON p.post_id = m.post_id "
                "WHERE p.dry_run=0 AND p.script_json IS NOT NULL "
                "AND m.reach >= 100").fetchall()
        finally:
            con.close()
        scored = []
        for sj, shares, reach in rows:
            try:
                s = _json.loads(sj)
                if not (s.get("reframe") or "").strip():
                    continue
                scored.append({**{k: s.get(k, "") for k in ("hook", "reframe", "cta")},
                               "sends_per_reach": round((shares or 0) / reach, 4)})
            except Exception:  # noqa: BLE001
                continue
        if len(scored) < 3:
            return []
        scored.sort(key=lambda e: e["sends_per_reach"], reverse=True)
        return scored[:n]
    except Exception:  # noqa: BLE001 - learning is optional
        return []


def digest_text(view: str, db_path=DEFAULT_DB) -> str:
    d = build_digest(db_path).get(view) or []
    if not d:
        return "No performance data yet."
    lines = ["Recent performance (sends-per-reach — copy what wins, avoid what dies):"]
    for e in d:
        lines.append(f"- [{e['rank']}] {e['sends_per_reach']:.1%} | arc={e['arc']} "
                     f"| hook: {e['hook'][:80]}")
    return "\n".join(lines)
