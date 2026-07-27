from unittest.mock import patch, MagicMock

from src.prompts import architect


def test_enhance_uses_official_sdk():
    """enhance_with_claude must instantiate anthropic.Anthropic and call messages.create."""
    pa = architect.PromptArchitect(anthropic_api_key="fake_key")
    with patch("anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="A cinematically-lit marble scene with golden hour light.")]
        )
        MockAnthropic.return_value = mock_client

        result = pa.enhance_with_claude(
            base_prompt="base", quote="Know thyself."
        )

    MockAnthropic.assert_called_once_with(api_key="fake_key")
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5"
    assert call_kwargs["max_tokens"] == 150
    assert "system" in call_kwargs
    assert "messages" in call_kwargs
    assert "cinematically-lit" in result


def test_enhance_falls_back_on_api_error():
    pa = architect.PromptArchitect(anthropic_api_key="fake_key")
    with patch("anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("network")
        MockAnthropic.return_value = mock_client
        result = pa.enhance_with_claude(base_prompt="ORIGINAL", quote="test")
    assert result == "ORIGINAL"