# Ship & Learn — Design

**Date:** 2026-07-12
**Status:** Approved (design)
**Follows:** the 3-sub-project quality program (reliability `e092f8d`, image/typography `b2c9e1c`, reel 3A `7161899`, reel 3B `92788f9`). This closes the ship-and-learn gaps that program deliberately left open.

## 1. Goal

The quality program made the *artifact* excellent, but three gaps mean that
artifact may never auto-ship reliably and its results may never feed the A/B
learner. Close them:

- **A5** — production is manual-publish-via-Telegram and never exercises the
  Graph-API publish path, which is therefore untested and rotting.
- **A6** — reconcile backfills `post_id` by fragile hook-substring matching;
  when the human edits the caption (the point of manual mode), the match fails
  and analytics silently drops that post from the learning loop.
- **C1** — sensitive/generated files are tracked and absolute local paths
  (`/Users/utsab1/…`) leak into both `logs/posts.jsonl` and the tracked
  `data/pipeline.db`.

All changes are additive and best-effort. No change to reel generation.

## 2. Decisions (locked)

| # | Decision |
|---|---|
| Publishing | **Keep `--manual` as the production default** (human adds trending audio — the #1 Reels reach lever). Do not switch to auto-publish. Guard the Graph-API path with a contract test + docs so it can't rot. |
| Reconcile | **Stable unique caption token** (short hashtag) as primary match; **timestamp-proximity** as no-cooperation fallback. |
| C1 mp3s | **Keep the 7 `audio/*.mp3` mood beds tracked** — they are bundled assets (`reel_composer.MOOD_AUDIO`), not junk. Make the exception explicit in `.gitignore`. |
| C1 history | Rewriting git history to purge already-committed absolute paths is **out of scope** (needs `filter-repo` + force-push; risky with a remote). Noted as a deferred follow-up. |

## 3. Non-goals (YAGNI)

- No cron/schedule change; no new auto-publish slot.
- No git-history rewrite.
- No change to the reel, VO, music, grade, zoom, SFX, or karaoke work.
- No new analytics features — only make existing reconcile robust.

## 4. Architecture (ordered low-risk → high-risk)

### 4.1 Stream C1 — stop the leak (`pipeline.py`, `src/core/*`, `.gitignore`, `daily_post.yml`)

**Path hygiene (the real fix).** Absolute paths enter two tracked sinks:
- `save_log` record (`pipeline.py:364`, written with `str(final_image_path)` /
  `str(reel_path)` at `:605`, `:1038`) → `logs/posts.jsonl`.
- `mark_posted` (`pipeline.py:958`, `:1003`) → `data/pipeline.db` (tracked).

Introduce a single helper, `_rel_path(p) -> str | None`, that renders a path
repo-relative (relative to the repo root; falls back to the basename if the
path is outside the repo, returns `None` for `None`). Route every image/reel
path written to `save_log` and `mark_posted` through it. This kills future
leaks in *both* sinks at the source.

**Untrack junk.** `git rm --cached` (all already gitignored — verified):
`output/*.jpg` (18), `server.log`, `logs/posts.jsonl`, and the 3 `.DS_Store`
(`./`, `docs/`, `docs/superpowers/`). Commit; confirm they stay ignored.

**Keep mood beds.** The 7 `audio/*.mp3` (`calm_stoic.mp3`,
`cinematic_hopeful.mp3`, `dark_philosophical.mp3`, `dramatic_ancient.mp3`,
`epic_warrior.mp3`, `mystical_greek.mp3`, `stark_minimal.mp3`) are required by
`reel_composer.MOOD_AUDIO`. They are currently tracked despite `audio/*.mp3`
being gitignored. Make the intent explicit by adding `!audio/<name>.mp3`
exceptions for exactly these 7 (mirrors the established `!data/pipeline.db`
pattern), so they are never accidentally dropped.

**Workflow.** `daily_post.yml:198` does `git add -f data/pipeline.db logs/`,
which re-commits `posts.jsonl` even after we untrack it. Narrow it to
force-add the DB plus only the log file(s) worth persisting
(`logs/notifications.jsonl` if present), excluding `posts.jsonl`. The existing
`upload-artifact path: logs/` step still captures the full logs per-run, so no
audit signal is lost.

### 4.2 Stream A6 — robust reconcile (`pipeline.py`, `studio/reconcile.py`, `src/core/data_store.py`)

**Token generation.** A pure `reconcile_token(row_id: int) -> str` returns a
short, stable, case-insensitive hashtag token, e.g. `#sq` + base36 of the row
id (`#sq1a`). Deterministic from the post row id; unique per post; contains
only `[a-z0-9]` after the `#`.

**Stamp the caption.** At caption assembly (studio path stamps
`visual_direction.caption_marker`; `pipeline.py:380`), append the token as the
final element of the caption text actually sent to Telegram, and store the
token (not the fragile hook) as the proposal's reconcile marker. Also record
the manual-send timestamp on the proposal (for the fallback). The token is one
extra hashtag on accounts that already stack hashtags — humans keep it.

**Match.** `studio/reconcile.py`:
- Primary: `match` returns the `post_id` whose caption **contains the token**.
- Fallback: when no token match, pick the nearest **unreconciled** media whose
  `timestamp` is within a bounded window (default 6h) of the proposal's
  recorded send time. If several are in-window, choose the closest in time.
  If none, return `None` (unchanged behavior — never raises).

`_marker_for` reads the stored token; a new helper reads the send timestamp.
Backward-compatible: proposals stamped with an old hook-only marker still
substring-match as before.

### 4.3 Stream A5 — guard the publish path (`instagram_poster` test, README)

**Contract smoke test.** Add a test that drives the real publish entry point
(`post_reel_to_instagram` / `post_to_instagram`) with a **mocked HTTP layer**
(no live network, no live post) and asserts the request contract: the
container-create call and the publish call are made with the expected
endpoint, media type, and caption/URL fields. This exercises the code path in
CI so it cannot silently rot while production stays on manual.

**README.** Add a short section: scheduled production is **manual-publish via
Telegram by design** (so a human can add trending audio); the Graph-API
auto-publish path exists but is opt-in (`not dry_run and not manual`) and is
covered only by the contract test, not by live posting.

## 5. Data flow

```
caption assembly ─► append reconcile_token(#sq<b36id>) ─► Telegram + stored on proposal
manual human post (caption kept, trending audio added) ─► IG media
reconcile: token-in-caption match ─► post_id
           └─ else timestamp-proximity (≤6h, nearest unreconciled) ─► post_id
mark_proposal_posted(post_id) ─► metrics.py can fetch ─► A/B learner sees the post

save_log / mark_posted ─► _rel_path() ─► repo-relative paths only (no /Users/… leak)
```

## 6. Error handling

- No token match and no in-window media → `reconcile` returns `None`, as today;
  never raises.
- `_rel_path` on a path outside the repo → basename; on `None` → `None`.
- Mocked-HTTP contract test never touches the network.
- Untracking is a one-time `git rm --cached`; the `.gitignore` exceptions keep
  needed assets tracked.

## 7. Testing

Python (3.11 `.venv`):
- `reconcile_token`: deterministic, unique per id, `[a-z0-9]`-only body.
- `reconcile.match`: token present → id; caption edited but token kept → id;
  token absent → timestamp-proximity picks nearest unreconciled in-window;
  nothing in-window → `None`.
- `_rel_path`: repo-relative for in-repo paths, basename for outside, `None`
  for `None`; `save_log`/`mark_posted` persist relative paths.
- A5: publish contract test asserts container-create + publish request shape
  against a mocked HTTP layer.
- Untracked files stay ignored (`git check-ignore`); the 7 mood beds remain
  tracked.
- Full suite green apart from the 2 pre-existing ffmpeg failures.

## 8. Files touched

| File | Change |
|---|---|
| `pipeline.py` | `_rel_path` helper; route `save_log`/`mark_posted` paths through it; stamp `reconcile_token` into caption + proposal + send timestamp |
| `src/core/data_store.py` | store reconcile token + send timestamp on proposals (column/migration if needed); ensure `mark_posted` persists relative paths |
| `studio/reconcile.py` | token match + timestamp-proximity fallback; read token + send time |
| `.gitignore` | `!audio/<name>.mp3` exceptions for the 7 mood beds |
| `.github/workflows/daily_post.yml` | narrow `git add -f … logs/` to exclude `posts.jsonl` |
| `README.md` (NEW/section) | document manual-publish-by-design + opt-in auto path |
| `tests/…` | token, match+fallback, `_rel_path`, publish contract, ignore checks |
| (untracked) | `git rm --cached` output/*.jpg, server.log, posts.jsonl, **/.DS_Store |
