import asyncio
import functools
import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from ..config import settings

logger = logging.getLogger(__name__)

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

CLIENT_CONFIG = {
    "web": {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uris": [settings.google_redirect_uri],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def get_google_auth_url(state: str) -> tuple[str, str | None]:
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES, state=state)
    flow.redirect_uri = settings.google_redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, getattr(flow, "code_verifier", None)


async def exchange_google_code(code: str, code_verifier: str | None = None) -> dict:
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    if code_verifier:
        flow.code_verifier = code_verifier

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, functools.partial(flow.fetch_token, code=code))

    creds: Credentials = flow.credentials
    return _creds_to_dict(creds)


async def refresh_google_token(tokens: dict) -> dict:
    creds = Credentials(
        token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )
    import google.auth.transport.requests as google_requests
    request = google_requests.Request()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, creds.refresh, request)
    return _creds_to_dict(creds)


async def get_google_account_email(tokens: dict) -> str:
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        resp.raise_for_status()
        return resp.json()["email"]


def _creds_to_dict(creds: Credentials) -> dict:
    expiry = creds.expiry
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": expiry.isoformat() if expiry else None,
        "scopes": list(creds.scopes or []),
    }
