import json
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
from cryptography.fernet import Fernet

from ..config import settings

logger = logging.getLogger(__name__)


class NoTokensError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class TokenStore:
    def __init__(self) -> None:
        self._fernet = Fernet(settings.token_encryption_key.encode())

    def _encrypt(self, data: dict) -> bytes:
        return self._fernet.encrypt(json.dumps(data).encode())

    def _decrypt(self, ciphertext: bytes) -> dict:
        return json.loads(self._fernet.decrypt(ciphertext))

    async def save_token(
        self, user_id: int, provider: str, account_email: str, tokens: dict
    ) -> None:
        encrypted = self._encrypt(tokens)
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                """
                INSERT INTO oauth_tokens (user_id, provider, account_email, encrypted_tokens, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (user_id, provider, account_email)
                DO UPDATE SET encrypted_tokens = excluded.encrypted_tokens,
                              updated_at = excluded.updated_at
                """,
                (user_id, provider, account_email, encrypted, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()

    async def get_valid_token(
        self, user_id: int, provider: str, account_email: str
    ) -> dict:
        """Return tokens, refreshing the access token if near expiry."""
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT encrypted_tokens FROM oauth_tokens WHERE user_id=? AND provider=? AND account_email=?",
                (user_id, provider, account_email),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            raise NoTokensError(f"No tokens stored for {provider}/{account_email}")

        tokens = self._decrypt(row["encrypted_tokens"])

        expiry_str = tokens.get("expiry")
        if expiry_str:
            expiry = datetime.fromisoformat(expiry_str)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) + timedelta(minutes=5)
            if expiry <= cutoff:
                tokens = await self._refresh(user_id, provider, account_email, tokens)

        return tokens

    async def delete_token(self, user_id: int, provider: str, account_email: str) -> None:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "DELETE FROM oauth_tokens WHERE user_id=? AND provider=? AND account_email=?",
                (user_id, provider, account_email),
            )
            await db.commit()

    async def _refresh(
        self, user_id: int, provider: str, account_email: str, tokens: dict
    ) -> dict:
        try:
            if provider == "google":
                from .google import refresh_google_token
                new_tokens = await refresh_google_token(tokens)
            elif provider == "microsoft":
                from .microsoft import refresh_microsoft_token
                new_tokens = await refresh_microsoft_token(tokens)
            else:
                raise ValueError(f"Unknown provider: {provider}")

            merged = {**tokens, **new_tokens}
            await self.save_token(user_id, provider, account_email, merged)
            logger.info("Refreshed %s token for %s", provider, account_email)
            return merged
        except Exception as exc:
            raise TokenExpiredError(
                f"{provider} token for {account_email} is expired. Please re-authenticate."
            ) from exc


token_store = TokenStore()
