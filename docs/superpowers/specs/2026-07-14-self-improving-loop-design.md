# Self-Improving Loop — Design Spec

**Date:** 2026-07-14
**Status:** Approved design → implementation
**Goal:** A self-learning loop that automatically **proposes improvements to the app's prompts and system knobs**, validates them, and (on human approval) promotes the winners — so content quality compounds over time instead of staying frozen at hand-written defaults.

---

## 1. Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| **Reward signal** | **Hybrid** — an LLM *critic* proposes+scores edits at cold-start (0 engagement data); real IG A/B (champion-challenger) gates promotion once metrics accrue. |
| **Improve targets** | All four, **unified + phased**: (1) agent prompts, (2) selection policy, (3) predictive-scoring weights, (4) music/visual direction. **Phase 1 = prompts.** |
| **Autonomy** | **Propose → Telegram approve.** The loop autonomously observes/analyzes/proposes; a human approves every promotion via the existing approve/reject Telegram flow. |
| **Cadence** | **Nightly cron + on-demand CLI** (`python optimize.py --run`). |

---

## 2. What already exists (reused, not rebuilt)

- `src/analytics/metrics.py` — fetches Meta Insights → `post_metrics` (the reward input).
- `src/analytics/weekly_brief.py`, `cohort_analysis.py` → `perf_brief.json` (top/dying hooks, moods, formats, slots).
- `studio/strategist.py` already injects `perf_brief` into its prompt each run (in-context adaptation).
- `src/video/predictive_scoring.py` — pre-publish reward model (weighted saves/comments/shares/reach) with hand-set weights. **Its reward weights are reused as the loop's reward function.**
- `data/pipeline.db` tables: `posts` (logs mood/hook_id/caption_variant/seed per post), `post_metrics`, `ab_results` (per-arm win/trial tallies), `proposals`, `token_state`.
- `src/core/approval.py` + `notifier.py` — Telegram inline approve/reject (`approve_<id>`/`reject_<id>`, `poll_once`).

**The gap this spec fills:** nothing versions or rewrites the prompts/knobs, nothing proposes edits from performance, nothing runs a champion-challenger experiment to validate an edit before it ships.

---

## 3. Core abstraction — the Optimizable registry

Every tunable knob is an **Optimizable asset**:

- `key` — e.g. `prompt.strategist.role`, `prompt.copywriter.draft`, `policy.mood`, `weights.predictive`, `prompt.music_director`.
- `kind` ∈ `{prompt, policy, weights}` — determines the proposer mechanic and the applier.
- **champion** version (currently active) + full **version history**.
- a **proposer** (per kind) that generates a challenger.
- an **applier** — how the champion value is injected into the running pipeline.

Three mechanics, one skeleton (Observe → Propose → Validate → Surface → Promote):
- **prompt** → *critic agent* rewrites the text; challenger validated on predicted score + live A/B.
- **policy** → *Thompson-sampling bandit* over discrete arms (mood/slot/hook-style/format); champion = current best arm distribution.
- **weights** → *numeric refit* of predictive-scoring weights from `post_metrics` (pure-Python ridge/logistic), run in **shadow mode** before proposal.

### Storage (new tables in `pipeline.db`, additive migrations)

```sql
opt_assets(key TEXT PK, kind TEXT, champion_version_id INTEGER, created_at TEXT)

opt_versions(
  id INTEGER PK, key TEXT, version_num INTEGER,
  value_json TEXT,          -- prompt text / arm-weights / weight-vector
  source TEXT,              -- 'seed' | 'critic' | 'bandit' | 'weightfit'
  rationale TEXT,           -- why the proposer made this edit
  predicted_delta REAL,     -- proposer's predicted improvement (cold-start signal)
  status TEXT,              -- 'champion' | 'challenger' | 'candidate' | 'retired' | 'rejected'
  created_at TEXT
)

opt_experiments(
  id INTEGER PK, key TEXT,
  champion_version_id INTEGER, challenger_version_id INTEGER,
  metric TEXT,              -- reward metric name
  status TEXT,              -- 'open' | 'evaluated' | 'promoted' | 'retired'
  opened_at TEXT, closed_at TEXT,
  result_json TEXT          -- per-arm samples, reward means, decision
)
```
Per-post attribution: add `posts.opt_versions_json` (map of `key → version_id` used to produce that post). Reuse `ab_results` for bandit arm tallies.

---

## 4. Prompt loading — the enabler for "improve its prompt"

Today the agent prompts are static Python constants (`_PREFIX`/`_ROLE`). We introduce a loader:

```python
# src/optimizer/prompt_store.py
def get(key: str, default: str) -> str:
    """Return the champion version's text for `key`, else the hardcoded default.
    Also lazily registers `key` with `default` as seed v1 on first call."""
```

Each studio agent changes from `role = _ROLE.format(...)` to
`role = prompt_store.get("strategist.role", _ROLE_DEFAULT).format(...)`.
The hardcoded default stays in code — it is the safety net and the seed champion (v1). No behavior change until a challenger is promoted. This is a surgical edit to `strategist.py`, `copywriter.py`, `trend_scout.py` (Phase 1 scope).

---

## 5. The loop (`src/optimizer/loop.py`, nightly)

1. **Observe** — `metrics.ingest()` pulls latest Meta insights → `post_metrics`. `reward.py` computes a scalar reward per post (reusing `predictive_scoring` weights: saves 3.0, shares 2.5, comments 2.0, reach 1.5) and attributes it to the version ids in `posts.opt_versions_json`.
2. **Evaluate open experiments** — for each `open` experiment with ≥ `MIN_SAMPLES` posts per arm and ≥ `MIN_DAYS`, compare challenger vs champion mean reward. Win by margin + safety-pass → emit a **promotion proposal** (Telegram). Loss → mark challenger `retired`.
3. **Propose challengers** — for assets with no open experiment:
   - **prompt** → `prompt_critic` agent: given champion text + `perf_brief` + top/dying examples + the viral-formula rubric, output `{candidate_text, rationale, predicted_delta}`. If `predicted_delta > 0` and guardrails pass → open an experiment (challenger vs champion).
   - **policy** → bandit updates arm posteriors from `ab_results`; if a non-incumbent arm's upper-confidence bound beats champion → propose shifting the arm distribution.
   - **weights** → if ≥ `MIN_FIT_SAMPLES`, refit; run **shadow** (log old vs new predicted-score divergence) for `SHADOW_DAYS` before proposing.
4. **Surface** — send pending promotion proposals to Telegram via `approval` (reuse `approve_<id>`/`reject_<id>`). Message shows: key, diff/summary, rationale, predicted or measured delta, sample size.
5. **Promote / reject** — `optimize.py --apply-decisions` polls Telegram (`poll_once`); on approve → challenger `status=champion`, bump `opt_assets.champion_version_id`, retire old champion; on reject → `status=rejected`.

**Cold-start behavior:** with 0 `post_metrics`, step 2 is a no-op and step 3-prompt runs the critic, whose challengers are scored by rubric + *predicted* engagement. Those still reach Telegram as proposals ("critic suggests strategist rewrite, predicted +X%, approve?"). The loop delivers value on day one and **auto-upgrades to real-A/B gating** as soon as posts have metrics — no code change, same experiment machinery.

**A/B mechanics on IG:** while an experiment is `open` for `key`, the pipeline picks champion vs challenger 50/50 per post and records the choice in `posts.opt_versions_json`. Reward accrues per arm; evaluation reuses `ab_results` semantics.

---

## 6. Guardrails (`src/optimizer/guardrails.py`)

Every challenger must pass **before** an experiment opens:
- **Safety** — `trend_sources.is_unsafe()` on any generated text.
- **Structural** — a rewritten prompt still contains all required `{placeholders}`; a weight vector has the right keys/finite values; an arm distribution sums to 1.
- **Schema canary** — one live dry `client.call(...)` with the challenger prompt must return schema-valid output (proves it won't break the pipeline).
- **Never-crash contract** — the optimizer is best-effort; any failure logs and skips. It never blocks or delays posting (mirrors the rest of the pipeline).
- **Rollback record** — the retired champion is retained; a promoted challenger that underperforms over the next `WATCH_POSTS` is flagged in the nightly report for one-tap revert.

---

## 7. Module layout (isolation)

```
src/optimizer/
  __init__.py
  registry.py         # Optimizable assets, DB tables + migrations, champion/version CRUD
  prompt_store.py     # get(key, default) loader used by studio agents
  reward.py           # reward(post_metrics) → scalar; version attribution
  experiments.py      # open/evaluate champion-challenger; bandit tally helpers
  proposers/
    prompt_critic.py  # critic agent (studio.client) → challenger prompt + rationale
    policy_bandit.py  # Thompson sampling over discrete arms          [Phase 2]
    weight_fit.py     # refit predictive_scoring weights (shadow)      [Phase 3]
  guardrails.py       # safety, placeholder/schema/canary validation
  loop.py             # nightly orchestration
optimize.py           # CLI: --run | --status | --apply-decisions | --dry-run
studio/critic.py      # critic agent role/prefix + settings entry
```
Surgical edits: studio agents load prompts via `prompt_store.get`; `data_store.log_post` records `opt_versions_json`; `daily_post.yml` adds the nightly optimize step; the pipeline consults open experiments to pick champion/challenger per post.

---

## 8. Testing

- **Unit:** prompt loader (default vs override, lazy seed); reward computation + attribution; experiment open/evaluate (win / lose / insufficient-sample); guardrail validators (placeholder preservation, safety, schema canary mocked); bandit posterior update; weight refit on synthetic data; registry CRUD + migrations.
- **Integration:** seeded fixture DB (fake posts+metrics) → loop produces the expected proposal; simulated Telegram approve flips champion; reject retires; rollback flag path.
- **Contract:** optimizer failure never blocks posting (inject exceptions, assert pipeline still posts).
- **Determinism:** critic/bandit tests mock the LLM/RNG seams so assertions are stable.

---

## 9. Phasing (scope control)

- **Phase 1 (this plan) — Prompts, end-to-end:** registry + prompt_store + reward + experiments + prompt_critic + guardrails + loop + CLI + Telegram proposals + wiring the 3 studio agents. Delivers "improve its prompt automatically" working at cold-start.
- **Phase 2 — Selection policy:** `policy_bandit` over mood/slot/hook/format on `ab_results`.
- **Phase 3 — Scoring weights:** `weight_fit` shadow → propose.
- **Phase 4 — Music/visual direction:** register `music_director` + `prompt_architect` as prompt assets.

Each later phase is a new registered optimizer on the same framework — no rework.

---

## 10. Success criteria

1. `python optimize.py --run` on the current (near-empty) DB produces at least one **critic-proposed prompt challenger** with a rationale, surfaced to Telegram — proving cold-start value.
2. Approving it via Telegram flips the champion; the next pipeline run loads the new prompt via `prompt_store.get`.
3. With seeded metrics, an open experiment **auto-evaluates** and only proposes promotion when the challenger wins by margin.
4. Full suite green; optimizer failures never block a post.
