import logging
from datetime import datetime, timedelta, timezone

import httpx

from ..auth.token_store import token_store
from .base import CalendarEvent, RateLimitError, with_retry

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@with_retry()
async def fetch_teams_calendar_events(user_id: int, account_email: str) -> list[CalendarEvent]:
    tokens = await token_store.get_valid_token(user_id, "microsoft", account_email)
    access_token = tokens["access_token"]

    now = datetime.now(timezone.utc)
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "startDateTime": start,
        "endDateTime": end,
        "$select": "subject,start,end,location,onlineMeeting,bodyPreview",
        "$top": "25",
        "$orderby": "start/dateTime",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/me/calendarView",
            headers={"Authorization": f"Bearer {access_token}", "Prefer": 'outlook.timezone="UTC"'},
            params=params,
        )

    if resp.status_code == 429:
        raise RateLimitError("Teams Calendar rate limit hit")
    resp.raise_for_status()

    events: list[CalendarEvent] = []
    for item in resp.json().get("value", []):
        start_dt = _parse_dt(item.get("start", {}).get("dateTime"))
        end_dt = _parse_dt(item.get("end", {}).get("dateTime"))

        meeting_url = ""
        online_meeting = item.get("onlineMeeting")
        if online_meeting:
            meeting_url = online_meeting.get("joinUrl", "")

        location = item.get("location", {}).get("displayName", "")

        events.append(CalendarEvent(
            account=f"teams:{account_email}",
            title=item.get("subject", "(no title)"),
            start_time=start_dt,
            end_time=end_dt,
            location=location,
            meeting_url=meeting_url,
            description_snippet=item.get("bodyPreview", "")[:300],
        ))

    return events


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)
