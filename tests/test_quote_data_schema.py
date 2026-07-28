from studio.types import QuoteData, QUOTE_DATA_SCHEMA


def test_quote_data_round_trip():
    """Dataclass survives to_dict/from_dict with all 11 fields."""
    raw = {
        "hook": "You will not finish this video.",
        "bridge": None,
        "quote": "We suffer more in imagination than in reality.",
        "cta": "Save this for the next time you spiral.",
        "caption": "Seneca hits different at 2am.",
        "hashtags": ["#stoicism", "#philosophy", "#seneca"],
        "mood": "stark",
        "attribution": "Seneca",
        "audience": "doomscrollers",
        "row_number": 42,
        "music_track_id": "jamendo-123",
        "flux_prompt": "Stoic marble bust, dramatic lighting",
    }
    qd = QuoteData.from_dict(raw)
    assert qd.to_dict() == raw


def test_quote_data_schema_required_fields():
    """Schema requires the 9 core fields; music_track_id and flux_prompt are optional."""
    required = set(QUOTE_DATA_SCHEMA["required"])
    assert {"hook", "quote", "cta", "caption", "hashtags",
            "mood", "attribution", "audience", "row_number"} <= required
    assert "music_track_id" not in required
    assert "flux_prompt" not in required


def test_quote_data_schema_bridge_optional():
    """bridge is optional and may be null (per spec: 4th scene only when bridge set)."""
    assert "bridge" not in QUOTE_DATA_SCHEMA["required"]
