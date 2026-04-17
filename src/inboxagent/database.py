import aiosqlite
from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_user_id INTEGER PRIMARY KEY,
    timezone         TEXT NOT NULL DEFAULT 'Europe/London',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    user_id          INTEGER NOT NULL,
    provider         TEXT NOT NULL,
    account_email    TEXT NOT NULL,
    encrypted_tokens BLOB NOT NULL,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, provider, account_email)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id              INTEGER PRIMARY KEY,
    max_emails           INTEGER NOT NULL DEFAULT 20,
    email_lookback_hours INTEGER NOT NULL DEFAULT 24,
    digest_hour          INTEGER NOT NULL DEFAULT 8,
    digest_minute        INTEGER NOT NULL DEFAULT 0
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def ensure_user(telegram_user_id: int) -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_user_id) VALUES (?)",
            (telegram_user_id,),
        )
        await db.execute(
            "INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)",
            (telegram_user_id,),
        )
        await db.commit()


async def get_user_accounts(user_id: int) -> list[tuple[str, str]]:
    """Return list of (provider, account_email) for a user."""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT provider, account_email FROM oauth_tokens WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()
