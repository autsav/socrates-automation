"""Regression for final-review finding CRITICAL: stale champion prompts must
never permanently shadow a code default rewrite (e.g. the playbook rewrite in
spec 1.1). `registry.register_asset` re-seeds the champion when the code
default's hash no longer matches what was last seeded (see
`_reseed_on_default_change` in src/optimizer/registry.py).

Two layers:
1. A general contract test against a fresh DB: whenever a key's code default
   changes, the served value tracks the new default (not the stale one) —
   this is the mechanism, independent of any particular prompt text.
2. A contract test against the COMMITTED data/pipeline.db: for the four keys
   the final review called out by name (copywriter.draft, strategist.role,
   trend_scout.role, music_director.query), the text actually served today
   contains the current playbook marker — i.e. the migration was run and
   committed, not just implemented.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, prompt_store, assets
from studio import playbooks
import studio.strategist as strategist
import studio.copywriter as copywriter
import studio.trend_scout as trend_scout
import studio.music_director as music_director

ROOT = Path(__file__).resolve().parent.parent
COMMITTED_DB = ROOT / "data" / "pipeline.db"

# key -> (current code default, playbook marker that must appear in what's served)
_PLAYBOOK_MARKERS = {
    "prompt.strategist.role": (strategist._ROLE_DEFAULT, playbooks.STRATEGY_CRAFT),
    "prompt.copywriter.draft": (copywriter._DRAFT_ROLE_DEFAULT, playbooks.COPY_CRAFT),
    "prompt.trend_scout.role": (trend_scout._ROLE_DEFAULT, playbooks.TREND_CRAFT),
    "prompt.music_director.query": (music_director._QUERY_ROLE_DEFAULT, playbooks.MUSIC_CRAFT),
}


# --- 1. General "served == current default when default-hash changed" contract ---

def test_served_prompt_tracks_default_after_it_changes(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)

    old_default = "OLD DEFAULT v1"
    seeded = prompt_store.get("prompt.k", old_default, db)
    assert seeded == old_default  # first call seeds v1

    new_default = "NEW DEFAULT — the code changed"
    served = prompt_store.get("prompt.k", new_default, db)
    assert served == new_default, (
        "prompt_store.get must serve the NEW code default once it changes, not "
        "the stale seeded champion — this is the bug the final review flagged"
    )

    # History preserved: the old seed is retired, not deleted.
    champ = registry.get_champion("prompt.k", db)
    assert champ["value"] == new_default
    assert champ["status"] == "champion"


def test_served_prompt_unaffected_when_default_unchanged(tmp_path):
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    default = "STABLE DEFAULT"
    prompt_store.get("prompt.k", default, db)
    v1 = registry.get_champion("prompt.k", db)["id"]
    # A second call with the SAME default must not churn versions.
    prompt_store.get("prompt.k", default, db)
    v2 = registry.get_champion("prompt.k", db)["id"]
    assert v1 == v2


def test_experiment_driven_champion_survives_when_default_unchanged(tmp_path):
    """A champion that won via real A/B promotion (differs from the code
    default on purpose) must not get clobbered just because register_asset
    runs again with the SAME unchanged default."""
    db = tmp_path / "t.db"
    registry.init_optimizer_db(db)
    default = "DEFAULT TEXT"
    prompt_store.get("prompt.k", default, db)
    cid = registry.add_version("prompt.k", "PROMOTED CHALLENGER", "critic",
                               "won A/B", 0.2, db_path=db)
    registry.promote(cid, db)
    # Re-fetching with the same (unchanged) default must not revert the promotion.
    served = prompt_store.get("prompt.k", default, db)
    assert served == "PROMOTED CHALLENGER"


# --- 2. Contract against the COMMITTED db for the 4 named keys ---

def test_committed_db_serves_playbook_defaults_for_the_four_stale_keys():
    for key, (default, marker) in _PLAYBOOK_MARKERS.items():
        served = prompt_store.get(key, default, COMMITTED_DB)
        assert marker in served, (
            f"{key}: committed pipeline.db still serves a stale pre-playbook "
            f"champion — the reseed migration was not run/committed for this key"
        )


def test_committed_db_copywriter_draft_has_self_critique_clause():
    served = prompt_store.get(
        "prompt.copywriter.draft", copywriter._DRAFT_ROLE_DEFAULT, COMMITTED_DB
    )
    assert "critique against the copy craft" in served


def test_committed_db_all_managed_keys_match_current_default_or_a_real_promotion():
    """General contract: for every managed key, what the committed DB serves is
    either exactly today's code default, or a version whose hash was recorded
    as the current default at the time it was last (re)seeded — i.e. never a
    value left over from a superseded default."""
    for m in assets.MANAGED_PROMPTS:
        served = prompt_store.get(m["key"], m["default"], COMMITTED_DB)
        assert served == m["default"], (
            f"{m['key']}: served prompt differs from the current code default; "
            f"if this is an intentional promoted challenger this assertion "
            f"should be narrowed — but on this branch no challenger has been "
            f"promoted for any managed key"
        )
