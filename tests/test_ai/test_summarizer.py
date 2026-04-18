from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inboxagent.ai.summarizer import _build_prompt, summarize_digest


def test_build_prompt_includes_emails(sample_emails, sample_events):
    prompt = _build_prompt(sample_emails, sample_events, [])
    assert "Alice" in prompt
    assert "Project update" in prompt
    assert "Team standup" in prompt


def test_build_prompt_snippet_truncated(sample_emails, sample_events):
    sample_emails[0].snippet = "x" * 600
    prompt = _build_prompt(sample_emails, sample_events, [])
    assert "x" * 501 not in prompt


def test_build_prompt_no_emails(sample_events):
    prompt = _build_prompt([], sample_events, [])
    assert "No new emails" in prompt


def test_build_prompt_includes_errors(sample_emails, sample_events):
    prompt = _build_prompt(sample_emails, sample_events, ["Outlook unavailable"])
    assert "Outlook unavailable" in prompt


@pytest.mark.asyncio
async def test_summarize_digest_calls_openai(sample_emails, sample_events):
    mock_message = MagicMock()
    mock_message.content = "Your digest summary"

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock(prompt_tokens=500, completion_tokens=100)

    mock_completions = MagicMock()
    mock_completions.create = AsyncMock(return_value=mock_response)

    mock_chat = MagicMock()
    mock_chat.completions = mock_completions

    mock_client = MagicMock()
    mock_client.chat = mock_chat

    with patch("inboxagent.ai.summarizer.AsyncOpenAI", return_value=mock_client):
        result = await summarize_digest(sample_emails, sample_events, [])

    assert result == "Your digest summary"
    mock_completions.create.assert_called_once()

    call_kwargs = mock_completions.create.call_args.kwargs
    messages = call_kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
