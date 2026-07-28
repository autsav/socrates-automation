"""Deterministic keyword-overlap quote picker for the social_strategist agent."""
from pipeline import Pipeline


class FakeExcel:
    def __init__(self, rows):
        self._rows = rows
    def all_rows(self):
        return self._rows


def test_match_quote_picks_highest_keyword_overlap():
    rows = [
        {"row_number": 1, "text": "Generic wisdom about life.", "theme": "general",
         "attribution": "Unknown", "mood": "stark"},
        {"row_number": 2, "text": "Doomscrolling kills focus; marcus aurelius knew this.",
         "theme": "focus", "attribution": "Marcus Aurelius", "mood": "stark"},
        {"row_number": 3, "text": "Aurelius on discipline and mornings.", "theme": "discipline",
         "attribution": "Marcus Aurelius", "mood": "hopeful"},
    ]
    p = Pipeline.__new__(Pipeline)
    p.excel_reader = FakeExcel(rows)
    pick = p._match_quote(["marcus aurelius", "doomscrolling"])
    assert pick is not None
    assert pick["row_number"] == 2


def test_match_quote_returns_none_below_threshold():
    rows = [
        {"row_number": 1, "text": "Unrelated content.", "theme": "general",
         "attribution": "X", "mood": "stark"},
    ]
    p = Pipeline.__new__(Pipeline)
    p.excel_reader = FakeExcel(rows)
    assert p._match_quote(["nonexistent", "topic"]) is None


def test_match_quote_is_deterministic():
    rows = [
        {"row_number": 5, "text": "aurelius on mornings", "theme": "x",
         "attribution": "Marcus Aurelius", "mood": "stark"},
        {"row_number": 9, "text": "aurelius on discipline", "theme": "y",
         "attribution": "Marcus Aurelius", "mood": "stark"},
    ]
    p = Pipeline.__new__(Pipeline)
    p.excel_reader = FakeExcel(rows)
    a = p._match_quote(["aurelius"])
    b = p._match_quote(["aurelius"])
    assert a == b
    assert a["row_number"] in (5, 9)  # deterministic tie-break