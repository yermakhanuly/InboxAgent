import asyncio
import logging
from datetime import datetime, timedelta, timezone

import msal
import httpx

from ..config import settings

logger = logging.getLogger(__name__)

SCOPES = ["Mail.Read", "Calendars.Read", "offline_access", "User.Read"]


def _build_msal_app() -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id=settings.microsoft_client_id,
        authority=f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}",
    )


def get_microsoft_auth_url(state: str) -> str:
    app = _build_msal_app()
    result = app.initiate_auth_code_flow(
        scopes=SCOPES,
        redirect_uri=settings.microsoft_redirect_uri,
        state=state,
    )
    return result["auth_uri"]


async def exchange_microsoft_code(code: str, state: str) -> dict:
    app = _build_msal_app()

    # MSAL needs the full auth response dict; simulate it
    auth_response = {
        "code": code,
        "state": state,
        "session_state": "",
    }

    # We need to re-initiate the flow to get the flow dict — store it temporarily via bot_data in handlers
    # For simplicity, perform the token exchange directly via httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "code": code,
                "redirect_uri": settings.microsoft_redirect_uri,
                "grant_type": "authorization_code",
                "scope": " ".join(SCOPES),
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return _response_to_dict(data)


async def refresh_microsoft_token(tokens: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
                "scope": " ".join(SCOPES),
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return _response_to_dict(data)


async def get_microsoft_account_email(tokens: dict) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        resp.raise_for_status()
        return resp.json()["mail"] or resp.json()["userPrincipalName"]


def get_microsoft_direct_auth_url(state: str) -> str:
    """Build auth URL directly without MSAL flow object (simpler for our ephemeral server approach)."""
    import urllib.parse
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "response_mode": "query",
    }
    base = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0/authorize"
    return f"{base}?{urllib.parse.urlencode(params)}"


def _response_to_dict(data: dict) -> dict:
    expires_in = data.get("expires_in", 3600)
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expiry": expiry,
        "token_type": data.get("token_type", "Bearer"),
    }
