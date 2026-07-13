"""Champion-prompt loader. Studio agents call get(key, default) instead of
using a static constant; the hardcoded default is the seed v1 + safety net."""
import logging
from src.optimizer import registry

log = logging.getLogger(__name__)


def get(key, default, db_path=registry.DB_PATH):
    try:
        registry.register_asset(key, "prompt", default, db_path)  # idempotent seed
        champ = registry.get_champion(key, db_path)
        return champ["value"] if champ else default
    except Exception as e:  # never break generation
        log.warning(f"[optimizer] prompt_store.get({key!r}) fell back to default ({e})")
        return default
