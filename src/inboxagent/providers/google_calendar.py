import asyncio
import logging
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.oauth2.credentials

from ..auth.token_store import token_store
from .base import CalendarEvent, RateLimitError, with_retry

logger = logging.getLogger(__name__)


def _build_service(access_token: str):
    creds = google.oauth2.credentials.Credentials(token=access_token)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


@with_retry()
async def fetch_google_calendar_events(user_id: int, account_email: str) -> list[CalendarEvent]:
    tokens = await token_store.get_valid_token(user_id, "google", account_email)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, tokens["access_token"], account_email)


def _fetch_sync(access_token: str, account_email: str) -> list[CalendarEvent]:
    service = _build_service(access_token)

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(hours=24)).isoformat()

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=25,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as exc:
        if exc.resp.status == 429:
            raise RateLimitError("Google Calendar rate limit hit") from exc
        raise

    events: list[CalendarEvent] = []
    for item in result.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})

        start_dt = _parse_dt(start.get("dateTime") or start.get("date"))
        end_dt = _parse_dt(end.get("dateTime") or end.get("date"))

        meeting_url = item.get("hangoutLink", "")
        if not meeting_url:
            for entry in item.get("conferenceData", {}).get("entryPoints", []):
                if entry.get("entryPointType") == "video":
                    meeting_url = entry.get("uri", "")
                    break

        description = item.get("description", "")[:300] if item.get("description") else ""

        events.append(CalendarEvent(
            account=f"gcal:{account_email}",
            title=item.get("summary", "(no title)"),
            start_time=start_dt,
            end_time=end_dt,
            location=item.get("location", ""),
            meeting_url=meeting_url,
            description_snippet=description,
        ))

    return events


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)
