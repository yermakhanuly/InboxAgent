"""Shared test fixtures."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inboxagent.providers.base import CalendarEvent, EmailMessage


@pytest.fixture
def sample_emails():
    now = datetime.now(timezone.utc)
    return [
        EmailMessage(
            account="gmail:test@example.com",
            sender="Alice <alice@example.com>",
            subject="Project update",
            snippet="Hi, just wanted to share the latest project update...",
            received_at=now - timedelta(hours=2),
            is_important=True,
        ),
        EmailMessage(
            account="outlook:test@company.com",
            sender="Bob <bob@company.com>",
            subject="Invoice #1234",
            snippet="Please find attached the invoice for last month...",
            received_at=now - timedelta(hours=5),
            is_important=False,
        ),
    ]


@pytest.fixture
def sample_events():
    now = datetime.now(timezone.utc)
    return [
        CalendarEvent(
            account="gcal:test@example.com",
            title="Team standup",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=1, minutes=30),
            meeting_url="https://meet.google.com/abc-defg-hij",
        ),
        CalendarEvent(
            account="teams:test@company.com",
            title="1:1 with manager",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            meeting_url="https://teams.microsoft.com/l/meetup-join/...",
        ),
    ]


@pytest.fixture
def mock_token_store():
    with patch("inboxagent.auth.token_store.token_store") as mock:
        mock.get_valid_token = AsyncMock(return_value={
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        })
        mock.save_token = AsyncMock()
        mock.delete_token = AsyncMock()
        yield mock
