# Script Writer v3 — Design Spec

**Date:** 2026-07-21
**Status:** Approved (Approach A: staged pipeline with conditional revision)
**Goal:** Four composed upgrades to story_writer: rubric subscores driving a conditional revision stage, a real quote pool the writer chooses from, an 8-variant hook-specialist pass, and self-learning from the account's own winning scripts.

## Locked decisions

| Decision | Choice |
|---|---|
| Architecture | Staged: 2 drafts → subscore pick → conditional revision → hook pass → gates |
| Revision trigger | Any subscore ≤ 4 OR total below threshold; ONE revision call max; never-worse guarantee |
| Hook pass model | sonnet (8 variants, 8 fixed psychological angles), coded `score_hook` picks |
| Quote pool | 15–20 unposted excel rows; chosen row swaps into quote_data and gets marked posted |
| Winner learning | Real scripts persisted via record_post_versions; top-2 by sends-per-reach injected via extra_context; static exemplars remain as floor |
| Cost bound | ≈$2.5–3.5/day at 3 posts (within $5 ceiling) |

## 1. Rubric subscores (`studio/rubric.py`)

`score_story_detailed(d: dict) -> dict` returning:
- `hook`, `escalation`, `cta`, `simplicity`: each 0–10 (normalized from the existing scalar signals: hook = concrete hits − abstractions + statement bonus; escalation = sentence-rhythm score; cta = specificity tier; simplicity = inverse long-word fraction)
- `total`: weighted float (backward-compatible ordering with `score_story` — `score_story` refactors to delegate)
- `weaknesses`: list of human-readable strings, one per subscore ≤ 4 (e.g. "hook lacks a concrete image or number", "escalation sentences run long — cut them shorter", "cta names no specific friend-type", "too many long words")
Pure; never raises; malformed → all zeros + empty weaknesses.

## 2. Quote-choice freedom

**`pipeline.py`:** new helper `_quote_pool(quote_data) -> list[dict]` — reads up to 20 unposted rows from excel (reusing `studio.run._build_pool` or equivalent light reader), each `{row_number, quote, attribution}`; today's row first. Best-effort: any failure → `[{today's row}]` (current behavior).
**`_build_story_beats`** passes the full pool to `write_story`. After a valid story returns: if `story["quote_row"] != quote_data["row_number"]`, swap `quote_data`'s `quote`, `attribution`, and `row_number` to the chosen row's values — the CHOSEN row is the consumed quote (marked posted downstream); slot accounting and material tracking are row-agnostic and unaffected. The existing pool-membership gate already rejects out-of-pool rows.

## 3. Conditional revision stage (`studio/story_writer.write_story`)

After rubric pick of the 2-draft winner:
- `detail = score_story_detailed(winner)`; trigger when `detail["weaknesses"]` non-empty OR `detail["total"] < REVISION_THRESHOLD` (constant, tuned so ~40% of drafts trigger).
- ONE revision call: role = same prompt; user message = "Your draft scored — " + per-subscore lines + weaknesses + "Rewrite the four beats fixing EXACTLY the named weaknesses. Keep every phrase that already works." + the draft JSON.
- Revised draft runs ALL gates (validate_story, validate_formula, quote-leak, pool-membership). Pass → revised ships if its `total` ≥ winner's total (never-worse); any failure → pre-revision winner ships.

## 4. Hook specialist (`studio/hook_specialist.py`, new)

- `HOOK_ANGLES = ("fear", "curiosity", "status", "absurdity", "loss", "time-urgency", "secret", "challenge")`
- `generate_hooks(client, story: dict, n=8) -> list[str]` — one sonnet call (`hook_specialist` role in settings: sonnet/medium), schema `{hooks: [str]}`, prompt: the final story + "write one hook per angle: … Each ≤15 words, a STATEMENT, addresses the viewer (you/your), opens a loop it does not resolve."
- `score_hook(hook: str) -> float` in `studio/rubric.py` — concreteness hits + specificity (numbers, named objects) + loop-strength (no resolution phrases, tension words) − abstractions.
- `pick_hook(candidates, fallback) -> str` — validates each (viewer-token check reused from validate_formula's tokenizer, ≤15 words, statement, no resolution phrases), scores survivors, returns max or `fallback`.
- Wiring in `write_story`: after the final story clears gates, `beat_hook = pick_hook(generate_hooks(...), story["beat_hook"])` — whole pass try/except → original hook. Role registered in BOTH `ROLE_MODELS` ("claude-sonnet-4-6") and `ROLE_EFFORT` ("medium") — the settings-registration gotcha.

## 5. Winner learning

- **Persistence:** in the pipeline publish path, `record_post_versions(row_id, {...existing..., "script": {"hook": ..., "reframe": ..., "cta": ...}})` when a story arc posted (read the existing versions call and extend its dict).
- **`performance_digest.winning_scripts(n=2, db_path=DEFAULT) -> list[dict]`** — joins posts (versions JSON parsed for script) × post_metrics, sends-per-reach ranked, reach ≥ 100, requires ≥3 scored scripts else `[]`.
- **Injection:** `_build_story_beats` appends to `extra_context`: "REAL WINNERS FROM THIS ACCOUNT (study what worked):\n" + hook/reframe-first-60-words/cta per winner. Cold-start: empty → nothing appended; static exemplars in-prompt remain the permanent floor.

## Cost & error handling

Per story script: 2 opus drafts + ~0.4 × opus revision + 1 sonnet hook pass. Every stage best-effort with the previous stage's output as fallback; the never-crash arc contract (reject → retry → fallback arc) is untouched.

## Testing

- Subscores: decomposition ordering vs score_story, weakness strings fire at ≤4, garbage → zeros.
- Quote swap: chosen ≠ today's row swaps quote/attribution/row_number; pool fetch failure → single quote; out-of-pool still rejected.
- Revision: trigger threshold; never-worse (revised lower total → original ships); gate failure → original.
- Hook pass: angle count, validation filters, score ordering (concrete beats abstract), fallback on API failure.
- Winners: <3 scored → []; formatting; injection only when non-empty.
- Gate: live script generation inspection + acceptance post.

## Not in scope

Unbounded loops, judge agents, punch-mode changes, new arcs, TTS/visual changes.
