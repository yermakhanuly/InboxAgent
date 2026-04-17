from datetime import datetime, timezone

from ..providers.base import CalendarEvent, EmailMessage


def format_emails_plain(emails: list[EmailMessage], errors: list[str]) -> str:
    lines = ["📧 *Recent Emails*\n"]

    for email in emails:
        importance = "🔴 " if email.is_important else ""
        lines.append(
            f"{importance}*From:* {email.sender}\n"
            f"*Subject:* {email.subject}\n"
            f"*Preview:* {email.snippet[:200]}\n"
            f"_{email.account}_\n"
        )

    for err in errors:
        lines.append(f"⚠️ {err}")

    return "\n".join(lines)


def format_events_plain(events: list[CalendarEvent], errors: list[str]) -> str:
    lines = ["📅 *Upcoming Events*\n"]

    for event in sorted(events, key=lambda e: e.start_time):
        time_str = f"{event.start_time.strftime('%H:%M')}–{event.end_time.strftime('%H:%M')}"
        link = f"\n🔗 {event.meeting_url}" if event.meeting_url else ""
        location = f"\n📍 {event.location}" if event.location else ""
        lines.append(f"🕐 {time_str} *{event.title}*{location}{link}\n_{event.account}_\n")

    for err in errors:
        lines.append(f"⚠️ {err}")

    return "\n".join(lines)
