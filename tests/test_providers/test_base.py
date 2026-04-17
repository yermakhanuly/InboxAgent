import asyncio
from unittest.mock import AsyncMock

import pytest

from inboxagent.providers.base import RateLimitError, with_retry


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_attempt():
    call_count = 0

    @with_retry(max_attempts=3)
    async def fn():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await fn()
    assert result == "ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_retries_on_rate_limit():
    call_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RateLimitError("rate limited")
        return "ok"

    result = await fn()
    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_raises_after_max_attempts():
    @with_retry(max_attempts=2, base_delay=0.01)
    async def fn():
        raise RateLimitError("always rate limited")

    with pytest.raises(RateLimitError):
        await fn()


@pytest.mark.asyncio
async def test_retry_does_not_retry_auth_errors():
    from inboxagent.auth.token_store import TokenExpiredError

    call_count = 0

    @with_retry(max_attempts=3, base_delay=0.01)
    async def fn():
        nonlocal call_count
        call_count += 1
        raise TokenExpiredError("expired")

    with pytest.raises(TokenExpiredError):
        await fn()

    assert call_count == 1  # Must not retry auth errors
