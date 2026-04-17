import asyncio
import logging
from datetime import datetime, timezone

from ..auth.token_store import NoTokensError, TokenExpiredError
from ..config import settings
from ..database import get_user_accounts
from ..providers.base import CalendarEvent, EmailMessage

logger = logging.getLogger(__name__)


async def fetch_emails_for_accounts(
    user_id: int,
    accounts: list[tuple[str, str]],
    hours_back: int = settings.email_lookback_hours,
) -> tuple[list[EmailMessage], list[str]]:
    tasks = []
    for provider, account_email in accounts:
        if provider == "google":
            from ..providers.gmail import fetch_gmail_emails
            tasks.append(asyncio.wait_for(fetch_gmail_emails(user_id, account_email), timeout=10.0))
        elif provider == "microsoft":
            from ..providers.outlook import fetch_outlook_emails
            tasks.append(asyncio.wait_for(fetch_outlook_emails(user_id, account_email), timeout=10.0))

    if not tasks:
        return [], []

    results = await asyncio.gather(*tasks, return_exceptions=True)

    emails: list[EmailMessage] = []
    errors: list[str] = []
    for (provider, account_email), result in zip(
        [(p, e) for p, e in accounts if p in ("google", "microsoft")], results
    ):
        if isinstance(result, Exception):
            label = f"{'Gmail' if provider == 'google' else 'Outlook'} ({account_email})"
            if isinstance(result, (NoTokensError, TokenExpiredError)):
                errors.append(f"{label} needs re-authentication — use /auth_{'google' if provider == 'google' else 'microsoft'}")
            else:
                errors.append(f"{label} unavailable: {type(result).__name__}")
            logger.warning("Email fetch failed for %s/%s: %s", provider, account_email, result)
        else:
            emails.extend(result)

    return emails, errors


async def fetch_events_for_accounts(
    user_id: int,
    accounts: list[tuple[str, str]],
) -> tuple[list[CalendarEvent], list[str]]:
    tasks = []
    for provider, account_email in accounts:
        if provider == "google":
            from ..providers.google_calendar import fetch_google_calendar_events
            tasks.append(asyncio.wait_for(fetch_google_calendar_events(user_id, account_email), timeout=10.0))
        elif provider == "microsoft":
            from ..providers.teams_calendar import fetch_teams_calendar_events
            tasks.append(asyncio.wait_for(fetch_teams_calendar_events(user_id, account_email), timeout=10.0))

    if not tasks:
        return [], []

    results = await asyncio.gather(*tasks, return_exceptions=True)

    events: list[CalendarEvent] = []
    errors: list[str] = []
    for (provider, account_email), result in zip(
        [(p, e) for p, e in accounts if p in ("google", "microsoft")], results
    ):
        if isinstance(result, Exception):
            label = f"{'Google Calendar' if provider == 'google' else 'Teams Calendar'} ({account_email})"
            if isinstance(result, (NoTokensError, TokenExpiredError)):
                errors.append(f"{label} needs re-authentication")
            else:
                errors.append(f"{label} unavailable: {type(result).__name__}")
            logger.warning("Calendar fetch failed for %s/%s: %s", provider, account_email, result)
        else:
            events.extend(result)

    return events, errors


async def build_digest(user_id: int) -> str:
    accounts = await get_user_accounts(user_id)

    if not accounts:
        return (
            "📭 No accounts connected.\n\n"
            "Use /auth_google to connect Gmail + Google Calendar, or "
            "/auth_microsoft to connect Outlook + Teams."
        )

    email_task = fetch_emails_for_accounts(user_id, accounts)
    events_task = fetch_events_for_accounts(user_id, accounts)
    (emails, email_errors), (events, event_errors) = await asyncio.gather(email_task, events_task)

    all_errors = email_errors + event_errors

    from ..ai.summarizer import summarize_digest
    return await summarize_digest(emails, events, all_errors)


async def fetch_emails_only(user_id: int) -> str:
    accounts = await get_user_accounts(user_id)
    emails, errors = await fetch_emails_for_accounts(user_id, accounts)

    if not emails and not errors:
        return ""

    from ..digest.formatter import format_emails_plain
    return format_emails_plain(emails, errors)


async def fetch_events_only(user_id: int) -> str:
    accounts = await get_user_accounts(user_id)
    events, errors = await fetch_events_for_accounts(user_id, accounts)

    if not events and not errors:
        return ""

    from ..digest.formatter import format_events_plain
    return format_events_plain(events, errors)
