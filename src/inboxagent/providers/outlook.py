import logging
from datetime import datetime, timedelta, timezone

import httpx

from ..auth.token_store import token_store
from ..config import settings
from .base import EmailMessage, RateLimitError, with_retry

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@with_retry()
async def fetch_outlook_emails(user_id: int, account_email: str) -> list[EmailMessage]:
    tokens = await token_store.get_valid_token(user_id, "microsoft", account_email)
    access_token = tokens["access_token"]

    since = (datetime.now(timezone.utc) - timedelta(hours=settings.email_lookback_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    params = {
        "$filter": f"isRead eq false and receivedDateTime ge {since}",
        "$select": "from,subject,bodyPreview,receivedDateTime,importance",
        "$top": str(settings.max_emails_per_provider),
        "$orderby": "receivedDateTime desc",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )

    if resp.status_code == 429:
        raise RateLimitError("Outlook rate limit hit")
    resp.raise_for_status()

    emails: list[EmailMessage] = []
    for item in resp.json().get("value", []):
        sender_info = item.get("from", {}).get("emailAddress", {})
        sender = f"{sender_info.get('name', '')} <{sender_info.get('address', '')}>".strip()

        received_str = item.get("receivedDateTime", "")
        try:
            received_at = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
        except ValueError:
            received_at = datetime.now(timezone.utc)

        emails.append(EmailMessage(
            account=f"outlook:{account_email}",
            sender=sender,
            subject=item.get("subject", "(no subject)"),
            snippet=item.get("bodyPreview", "")[:500],
            received_at=received_at,
            is_important=item.get("importance", "normal") == "high",
            message_id=item.get("id", ""),
        ))

    return emails
