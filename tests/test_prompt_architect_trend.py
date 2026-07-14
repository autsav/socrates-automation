import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.prompts.architect import PromptArchitect


def test_trend_topic_appears_in_prompt():
    p = PromptArchitect().build(quote="Know thyself.", mood="dark_philosophical",
                                trend_topic="World Cup final", seed=1)
    assert "World Cup" in p


def test_no_trend_topic_unchanged():
    a = PromptArchitect().build(quote="Know thyself.", mood="dark_philosophical", seed=1)
    b = PromptArchitect().build(quote="Know thyself.", mood="dark_philosophical",
                                trend_topic="", seed=1)
    assert a == b
