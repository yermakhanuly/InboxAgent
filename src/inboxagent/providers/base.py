import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    account: str       # "gmail:user@example.com"
    sender: str
    subject: str
    snippet: str       # max 500 chars — never the full body
    received_at: datetime
    is_important: bool = False
    message_id: str = ""


@dataclass
class CalendarEvent:
    account: str       # "gcal:user@example.com"
    title: str
    start_time: datetime
    end_time: datetime
    location: str = ""
    meeting_url: str = ""
    description_snippet: str = ""


class RateLimitError(Exception):
    pass


def with_retry(max_attempts: int = 3, base_delay: float = 1.0):
    """Exponential backoff with jitter for provider API calls."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except RateLimitError as exc:
                    last_exc = exc
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        "Rate limited on %s attempt %d/%d, retrying in %.1fs",
                        func.__name__, attempt + 1, max_attempts, delay,
                    )
                    await asyncio.sleep(delay)
                except Exception as exc:
                    # Don't retry auth errors
                    from ..auth.token_store import NoTokensError, TokenExpiredError
                    if isinstance(exc, (NoTokensError, TokenExpiredError)):
                        raise
                    if attempt == max_attempts - 1:
                        raise
                    last_exc = exc
                    await asyncio.sleep(base_delay * (2 ** attempt))
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
