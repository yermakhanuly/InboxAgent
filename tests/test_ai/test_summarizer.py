from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inboxagent.ai.summarizer import _build_prompt, summarize_digest


def test_build_prompt_includes_emails(sample_emails, sample_events):
    prompt = _build_prompt(sample_emails, sample_events, [])
    assert "Alice" in prompt
    assert "Project update" in prompt
    assert "Team standup" in prompt


def test_build_prompt_snippet_truncated(sample_emails, sample_events):
    # Artificially long snippet
    sample_emails[0].snippet = "x" * 600
    prompt = _build_prompt(sample_emails, sample_events, [])
    # Snippet in prompt should not exceed 500 chars
    assert "x" * 501 not in prompt


def test_build_prompt_no_emails(sample_events):
    prompt = _build_prompt([], sample_events, [])
    assert "No new emails" in prompt


def test_build_prompt_includes_errors(sample_emails, sample_events):
    prompt = _build_prompt(sample_emails, sample_events, ["Outlook unavailable"])
    assert "Outlook unavailable" in prompt


@pytest.mark.asyncio
async def test_summarize_digest_calls_claude(sample_emails, sample_events):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Your digest summary")]
    mock_response.usage = MagicMock(
        cache_creation_input_tokens=100,
        cache_read_input_tokens=0,
        input_tokens=500,
    )

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch("inboxagent.ai.summarizer.anthropic.AsyncAnthropic", return_value=mock_client):
        result = await summarize_digest(sample_emails, sample_events, [])

    assert result == "Your digest summary"
    mock_client.messages.create.assert_called_once()

    # Verify prompt caching is set on the system prompt
    call_kwargs = mock_client.messages.create.call_args.kwargs
    system = call_kwargs["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
