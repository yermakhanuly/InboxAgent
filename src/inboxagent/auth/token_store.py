import json
import logging
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet

from ..config import settings
from ..database import get_pool

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
        async with get_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO oauth_tokens (user_id, provider, account_email, encrypted_tokens, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id, provider, account_email)
                DO UPDATE SET encrypted_tokens = EXCLUDED.encrypted_tokens,
                              updated_at = EXCLUDED.updated_at
                """,
                user_id, provider, account_email, encrypted,
                datetime.now(timezone.utc),
            )

    async def get_valid_token(
        self, user_id: int, provider: str, account_email: str
    ) -> dict:
        """Return tokens, refreshing the access token if near expiry."""
        async with get_pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT encrypted_tokens FROM oauth_tokens WHERE user_id=$1 AND provider=$2 AND account_email=$3",
                user_id, provider, account_email,
            )

        if not row:
            raise NoTokensError(f"No tokens stored for {provider}/{account_email}")

        tokens = self._decrypt(bytes(row["encrypted_tokens"]))

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
        async with get_pool().acquire() as conn:
            await conn.execute(
                "DELETE FROM oauth_tokens WHERE user_id=$1 AND provider=$2 AND account_email=$3",
                user_id, provider, account_email,
            )

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
