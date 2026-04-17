import logging
from datetime import datetime, timezone

import anthropic

from ..config import settings
from ..providers.base import CalendarEvent, EmailMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are InboxAgent, an AI assistant that creates concise daily digests for a single user.

Rules:
- Summarize emails by topic/sender cluster, not individually, unless an email is urgent or requires action
- Use these prefixes: ⚡ for action items, ℹ️ for FYI items, 🔴 for urgent items
- For calendar events: list time (HH:MM), title, and joining link if available
- Never reproduce full email content — work only from subjects and snippets provided
- Format in plain readable text (no MarkdownV2 special chars unless escaped)
- Keep the total digest under 3000 characters
- If a provider had an error, include a brief note like "⚠️ Outlook unavailable"
- Group by source: Emails first, then Calendar
- Be concise and direct — this is a personal digest, not a report"""


async def summarize_digest(
    emails: list[EmailMessage],
    events: list[CalendarEvent],
    provider_errors: list[str],
) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    user_content = _build_prompt(emails, events, provider_errors)

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    logger.debug(
        "Summarizer usage — cache_write: %s, cache_read: %s, uncached: %s",
        getattr(response.usage, "cache_creation_input_tokens", 0),
        getattr(response.usage, "cache_read_input_tokens", 0),
        response.usage.input_tokens,
    )

    return response.content[0].text


def _build_prompt(
    emails: list[EmailMessage],
    events: list[CalendarEvent],
    provider_errors: list[str],
) -> str:
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    lines = [f"Please create today's digest for {today}.\n"]

    if provider_errors:
        lines.append("## PROVIDER ERRORS")
        for err in provider_errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("## EMAILS")
    if emails:
        for email in emails:
            importance = " [IMPORTANT]" if email.is_important else ""
            lines.append(
                f"- [{email.account}]{importance} From: {email.sender} | "
                f"Subject: {email.subject} | "
                f"Preview: {email.snippet[:500]}"
            )
    else:
        lines.append("- No new emails")

    lines.append("\n## CALENDAR EVENTS (next 24 hours)")
    if events:
        for event in sorted(events, key=lambda e: e.start_time):
            link = f" | Join: {event.meeting_url}" if event.meeting_url else ""
            loc = f" @ {event.location}" if event.location else ""
            lines.append(
                f"- [{event.account}] {event.start_time.strftime('%H:%M')}–"
                f"{event.end_time.strftime('%H:%M')} {event.title}{loc}{link}"
            )
    else:
        lines.append("- No events today")

    return "\n".join(lines)
