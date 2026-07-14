"""Champion-prompt loader. Studio agents call get(key, default) instead of
using a static constant; the hardcoded default is the seed v1 + safety net.

A/B arm-serving is OPT-IN per run and requires no change to agent code:
- pipeline calls begin_run(seed) before generating a post,
- get() then returns the *challenger* text for any key with an open experiment
  on ~half of runs (deterministic by seed) and the champion otherwise,
- pipeline calls run_versions() to record {key: version_id} on the post, and
  end_run() to clear. With no begin_run() call, get() always returns the champion.
"""
import logging
from src.optimizer import registry, experiments

log = logging.getLogger(__name__)

# Run-scoped arm assignment: {key: {"value": str, "version_id": int}} or None.
_ARM_CONTEXT = None


def begin_run(seed, db_path=registry.DB_PATH):
    """Assign champion/challenger arms for every open experiment, deterministically
    by `seed` (so a given post is stable), for the duration of this run. Best-effort."""
    global _ARM_CONTEXT
    ctx = {}
    try:
        for a in _managed_keys(db_path):
            exp = experiments.get_open_experiment(a, db_path)
            if not exp:
                continue
            use_challenger = (int(seed) + hash(a)) % 2 == 0
            vid = exp["challenger_version_id"] if use_challenger else exp["champion_version_id"]
            v = registry.get_version(vid, db_path)
            if v:
                ctx[a] = {"value": v["value"], "version_id": vid}
    except Exception as e:  # never break generation
        log.warning(f"[optimizer] begin_run failed ({e}) — champions only")
        ctx = {}
    _ARM_CONTEXT = ctx


def _managed_keys(db_path):
    # Local import avoids a circular import (assets imports studio -> prompt_store).
    from src.optimizer import assets
    return [m["key"] for m in assets.MANAGED_PROMPTS]


def run_versions():
    """{key: version_id} chosen this run — record on the post for A/B attribution."""
    if not _ARM_CONTEXT:
        return {}
    return {k: v["version_id"] for k, v in _ARM_CONTEXT.items()}


def end_run():
    global _ARM_CONTEXT
    _ARM_CONTEXT = None


def get(key, default, db_path=registry.DB_PATH):
    try:
        # In an A/B run this key may be assigned to the challenger arm.
        if _ARM_CONTEXT and key in _ARM_CONTEXT:
            return _ARM_CONTEXT[key]["value"]
        registry.register_asset(key, "prompt", default, db_path)  # idempotent seed
        champ = registry.get_champion(key, db_path)
        return champ["value"] if champ else default
    except Exception as e:  # never break generation
        log.warning(f"[optimizer] prompt_store.get({key!r}) fell back to default ({e})")
        return default
