import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content.trend_sources import is_unsafe


def test_sports_topics_allowed():
    for t in ["World Cup final", "football transfer news", "Olympic gold medal"]:
        assert is_unsafe(t) is False, t


def test_unsafe_topics_rejected():
    for t in ["war casualties", "fatal crash", "shooting victims"]:
        assert is_unsafe(t) is True, t
