import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import google.oauth2.credentials

from ..auth.token_store import token_store
from ..config import settings
from .base import EmailMessage, RateLimitError, with_retry

logger = logging.getLogger(__name__)


def _build_service(access_token: str):
    creds = google.oauth2.credentials.Credentials(token=access_token)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


@with_retry()
async def fetch_gmail_emails(user_id: int, account_email: str) -> list[EmailMessage]:
    tokens = await token_store.get_valid_token(user_id, "google", account_email)
    access_token = tokens["access_token"]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, access_token, account_email)


def _fetch_sync(access_token: str, account_email: str) -> list[EmailMessage]:
    service = _build_service(access_token)
    since = (datetime.now(timezone.utc) - timedelta(hours=settings.email_lookback_hours))
    since_epoch = int(since.timestamp())

    query = f"(is:unread OR is:starred) in:inbox after:{since_epoch}"

    try:
        result = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=settings.max_emails_per_provider,
        ).execute()
    except HttpError as exc:
        if exc.resp.status == 429:
            raise RateLimitError("Gmail rate limit hit") from exc
        raise

    messages_meta = result.get("messages", [])
    if not messages_meta:
        return []

    emails: list[EmailMessage] = []
    for meta in messages_meta:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=meta["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()

            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            snippet = msg.get("snippet", "")[:500]
            label_ids = msg.get("labelIds", [])

            received_str = headers.get("Date", "")
            try:
                received_at = parsedate_to_datetime(received_str)
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=timezone.utc)
            except Exception:
                received_at = datetime.now(timezone.utc)

            emails.append(EmailMessage(
                account=f"gmail:{account_email}",
                sender=headers.get("From", "Unknown"),
                subject=headers.get("Subject", "(no subject)"),
                snippet=snippet,
                received_at=received_at,
                is_important="IMPORTANT" in label_ids or "STARRED" in label_ids,
                message_id=meta["id"],
            ))
        except HttpError:
            logger.warning("Failed to fetch Gmail message %s", meta["id"])

    return emails
