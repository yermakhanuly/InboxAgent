import pytest
from inboxagent.digest.formatter import format_emails_plain, format_events_plain


def test_format_emails_plain(sample_emails):
    result = format_emails_plain(sample_emails, [])
    assert "Alice" in result
    assert "Project update" in result
    assert "Invoice" in result
    assert "gmail:test@example.com" in result


def test_format_emails_with_errors(sample_emails):
    errors = ["Gmail (test@example.com) needs re-authentication"]
    result = format_emails_plain(sample_emails, errors)
    assert "⚠️" in result
    assert "re-authentication" in result


def test_format_events_plain(sample_events):
    result = format_events_plain(sample_events, [])
    assert "Team standup" in result
    assert "meet.google.com" in result
    assert "1:1 with manager" in result


def test_format_events_empty():
    result = format_events_plain([], [])
    assert "Events" in result


def test_format_emails_marks_important(sample_emails):
    result = format_emails_plain(sample_emails, [])
    # The important email should have a red indicator
    assert "🔴" in result
