from unittest.mock import AsyncMock, patch

import pytest

from inboxagent.digest.builder import fetch_emails_for_accounts, fetch_events_for_accounts
from inboxagent.auth.token_store import TokenExpiredError


@pytest.mark.asyncio
async def test_fetch_emails_empty_accounts():
    emails, errors = await fetch_emails_for_accounts(123, [])
    assert emails == []
    assert errors == []


@pytest.mark.asyncio
async def test_fetch_emails_token_expired(mock_token_store):
    mock_token_store.get_valid_token.side_effect = TokenExpiredError("expired")

    with patch("inboxagent.providers.gmail.token_store", mock_token_store):
        emails, errors = await fetch_emails_for_accounts(123, [("google", "test@example.com")])

    assert emails == []
    assert len(errors) == 1
    assert "re-authentication" in errors[0]


@pytest.mark.asyncio
async def test_fetch_emails_success(mock_token_store, sample_emails):
    with patch("inboxagent.providers.gmail.token_store", mock_token_store), \
         patch("inboxagent.providers.gmail.fetch_gmail_emails", AsyncMock(return_value=sample_emails[:1])):
        emails, errors = await fetch_emails_for_accounts(123, [("google", "test@example.com")])

    assert len(emails) == 1
    assert errors == []


@pytest.mark.asyncio
async def test_fetch_events_empty_accounts():
    events, errors = await fetch_events_for_accounts(123, [])
    assert events == []
    assert errors == []
