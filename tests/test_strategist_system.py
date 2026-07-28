from studio.prompts.strategist_system import SYSTEM_PROMPT, SHARED_PREFIX


def test_system_prompt_contains_all_sections():
    """All 7 sections of the 2026 framework are present."""
    for section in [
        "Role & Persona",
        "Platform Mastery: Instagram",
        "Platform Mastery: TikTok",
        "Psychology & The 3-Second Hook",
        "Copywriting & Scripting Frameworks",
        "Engagement & Community Building",
        "Output Instructions",
    ]:
        assert section in SYSTEM_PROMPT, f"Missing section: {section}"


def test_system_prompt_has_schema_directive():
    """The appended schema directive is present."""
    assert "QuoteData schema" in SYSTEM_PROMPT
    assert "Hook" in SYSTEM_PROMPT and "12 words" in SYSTEM_PROMPT
    assert "3-5 hashtags" in SYSTEM_PROMPT
    assert "engagement-bait" in SYSTEM_PROMPT.lower()


def test_shared_prefix_mentions_instagram():
    """Prefix names the platform (Instagram primary per spec)."""
    assert "Instagram" in SHARED_PREFIX