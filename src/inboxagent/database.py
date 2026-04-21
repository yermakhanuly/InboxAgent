import asyncpg

from .config import settings

_pool: asyncpg.Pool | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_user_id BIGINT PRIMARY KEY,
    timezone         TEXT NOT NULL DEFAULT 'Europe/London',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    user_id          BIGINT NOT NULL,
    provider         TEXT NOT NULL,
    account_email    TEXT NOT NULL,
    encrypted_tokens BYTEA NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, provider, account_email)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id              BIGINT PRIMARY KEY,
    max_emails           INTEGER NOT NULL DEFAULT 20,
    email_lookback_hours INTEGER NOT NULL DEFAULT 24,
    digest_hour          INTEGER NOT NULL DEFAULT 8,
    digest_minute        INTEGER NOT NULL DEFAULT 0
);
"""


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, ssl="require")
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_db() first")
    return _pool


async def ensure_user(telegram_user_id: int) -> None:
    async with get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO users (telegram_user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            telegram_user_id,
        )
        await conn.execute(
            "INSERT INTO user_preferences (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            telegram_user_id,
        )


async def get_user_accounts(user_id: int) -> list[tuple[str, str]]:
    """Return list of (provider, account_email) for a user."""
    async with get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT provider, account_email FROM oauth_tokens WHERE user_id = $1",
            user_id,
        )
    return [(row["provider"], row["account_email"]) for row in rows]
