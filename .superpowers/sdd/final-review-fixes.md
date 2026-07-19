# Final Review Fixes — world-class-agents branch

Commit: fix(agents): re-seed stale champions on default change; de-race DB pushes; digest-feed daily optimizer; true dry-run

## CRITICAL — stale champion prompts shadow the new playbook defaults

Root cause: `registry.register_asset(key, kind, seed_value, db_path)` only wrote a
version when `opt_assets.champion_version_id IS NULL`. Once a key was seeded
(v1), any later change to the code-side default (e.g. embedding a playbook)
was silently ignored forever — the stored v1 stayed champion.

Fix (`src/optimizer/registry.py`):
- Added `opt_assets.default_hash` (additive migration, `_ensure_default_hash_column`,
  idempotent — backfills every existing key's hash from its `version_num=1` row so
  keys whose default never changed do NOT spuriously re-version).
- `register_asset` now compares `sha256(seed_value)` against the stored
  `default_hash`. On mismatch, `_reseed_on_default_change` inserts the new
  default as a fresh champion version (`source='default-reseed'`), retires
  the prior champion (status flips to `retired`, row kept — history
  preserved, nothing deleted), and updates `opt_assets.champion_version_id`
  + `default_hash`. On match, behavior is unchanged (idempotent, no churn).

Migration run against the committed `data/pipeline.db`: called
`assets.iter_managed()` once (imports the 4 affected studio modules, calls
`prompt_store.get` for every managed key, which drives `register_asset`).
Confirmed via query that `prompt.copywriter.draft`, `prompt.strategist.role`,
`prompt.trend_scout.role`, `prompt.music_director.query` each got a new
`version_num=2 / source=default-reseed / status=champion` row, with the old
`version_num=1 / source=seed` row flipped to `retired`. The other 5 managed
keys (`strategist.prefix`, `copywriter.revise`, `music_director.rank`,
`story_writer.role`) were untouched — their backfilled hash already matched
the current default, so no reseed fired. Then ran
`DELETE FROM token_state` and committed the updated `data/pipeline.db`.

Regression test: `tests/test_champion_default_drift.py`
- General contract (fresh tmp DB): `prompt_store.get(key, default)` tracks a
  changed default, is idempotent when the default is unchanged, and a
  real experiment-promoted champion is NOT clobbered by a later call with the
  same (unchanged) default.
- Committed-DB contract: for the 4 named keys, the text served by
  `prompt_store.get(key, default, COMMITTED_DB)` contains the current
  playbook marker (`playbooks.STRATEGY_CRAFT` / `COPY_CRAFT` / `TREND_CRAFT`
  / `MUSIC_CRAFT`) and the copywriter draft prompt additionally contains the
  self-critique clause. A whole-registry contract asserts every managed key
  currently serves exactly its code default (no manual promotions exist yet
  on this branch).

Existing tests updated to match the new (correct) semantics:
- `tests/test_optimizer_registry.py::test_register_is_idempotent` renamed/
  split into `test_register_is_idempotent_when_default_unchanged` (kept) +
  new `test_register_reseeds_champion_when_code_default_changes` (was
  asserting the bug: "seed not overwritten" when a *different* value is
  passed) + `test_register_does_not_reseed_a_promoted_experiment_champion_repeatedly`.
- `tests/test_optimizer_arm_serving.py::test_no_run_context_serves_champion`
  and `::test_end_run_restores_champion` previously called `get(key, "DEF",
  db)` against a fixture seeded with `"CHAMP {x}"` — a mismatched literal
  that only worked because of the bug. Real call sites always pass the same
  constant default; updated both to pass `"CHAMP {x}"` (the actually-seeded
  default) so the assertions reflect real usage. The other two tests in that
  file are unaffected — they exercise the `begin_run`/challenger path, which
  returns from `_ARM_CONTEXT` before ever reaching `register_asset`.

## IMPORTANT 1 — Monday push race

`.github/workflows/optimizer.yml` cron moved `0 8 * * 1` → `0 9 * * 1`
(1h after `analytics.yml`'s daily/Monday 08:00 UTC run). Both workflows'
"Commit SQLite database back to repo" steps now run
`git pull --rebase --autostash origin "${GITHUB_REF_NAME}"` immediately
before `git push`, so a concurrent push from the sibling workflow rebases
instead of rejecting non-fast-forward.

## IMPORTANT 2 — daily optimizer preempts the weekly digest-fed one

`optimize.py::_perf_context(db_path)` now best-effort appends
`src.analytics.performance_digest.digest_text("story_writer", db_path)` to
the perf-brief context it already builds (try/except → `""` on any
failure, so cold-start / missing tables never break the daily run). Since
`_perf_context` feeds both `--run` and `--dry-run` (`loop.run_once(client,
_perf_context(db_path), ...)`), both paths are now digest-informed;
`loop.run_once`'s existing "skip keys with an open experiment" behavior is
unchanged — no experiment-lifecycle restructuring.

## MINOR — run_optimizer --dry-run false claim

`scripts/run_optimizer.py::main(dry_run=True)` no longer calls
`loop.run_once` (which queued a challenger version + opened an experiment +
spent an API call despite printing "not queued"). Under `dry_run`, after
`evaluate_experiments()`, it now lists the managed prompts that WOULD be
considered via `src.optimizer.assets.iter_managed()` (DB read only, no
client, no API call) and returns `0`.

`tests/test_run_optimizer.py` updated:
- `test_main_passes_digest_as_perf_context` moved to the non-dry
  (`dry_run=False`) path, since digest-context is now only passed to
  `run_once` on that path.
- `test_main_dry_run_never_surfaces` no longer stubs `loop.run_once` (not
  called under dry-run).
- New `test_main_dry_run_skips_run_once_no_api_call`: stubs `loop.run_once`
  and `_client` to raise `AssertionError` if called; monkeypatches
  `assets.iter_managed`; asserts `rc == 0` and the printed output lists the
  managed key(s) and still says "not queued" — now truthfully.

## Test evidence

```
$ .venv/bin/python -m pytest tests/test_run_optimizer.py tests/test_optimizer_wiring.py \
    tests/test_champion_default_drift.py tests/test_workflow_reliability.py \
    tests/test_optimizer_registry.py -q
..................................                                       [100%]
34 passed in 0.46s

$ .venv/bin/python -m pytest -q
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 51%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 92%]
.......................................................                  [100%]
703 passed, 1 warning in 90.26s (0:01:30)

$ .venv/bin/python -c "import sqlite3; c=sqlite3.connect('data/pipeline.db'); \
    print(c.execute('SELECT count(*) FROM token_state').fetchone()[0])"
0
```
