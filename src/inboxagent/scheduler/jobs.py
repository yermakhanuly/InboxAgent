import logging

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from ..config import settings

logger = logging.getLogger(__name__)


def setup_scheduler(application: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.app = application  # type: ignore[attr-defined]
    return scheduler


async def schedule_digest(application: Application) -> None:
    """Add the daily digest cron job for the configured user."""
    scheduler: AsyncIOScheduler = application.bot_data["scheduler"]
    user_id = settings.telegram_user_id
    tz = pytz.timezone(settings.default_timezone)

    job_id = f"digest_{user_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        func=send_daily_digest,
        trigger=CronTrigger(
            hour=settings.digest_hour,
            minute=settings.digest_minute,
            timezone=tz,
        ),
        id=job_id,
        kwargs={"user_id": user_id, "application": application},
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    logger.info(
        "Daily digest scheduled for user %d at %02d:%02d %s",
        user_id, settings.digest_hour, settings.digest_minute, settings.default_timezone,
    )


async def send_daily_digest(user_id: int, application: Application) -> None:
    logger.info("Sending daily digest to user %d", user_id)
    try:
        from ..digest.builder import build_digest
        from ..bot.messages import chunk_message

        digest_text = await build_digest(user_id)
        chunks = chunk_message(digest_text)

        for chunk in chunks:
            await application.bot.send_message(
                chat_id=user_id,
                text=chunk,
            )
        logger.info("Daily digest sent to user %d (%d chunk(s))", user_id, len(chunks))

    except Exception:
        logger.exception("Failed to send daily digest to user %d", user_id)
        try:
            from ..auth.token_store import TokenExpiredError
            # Error already logged; send a short Telegram notice
            await application.bot.send_message(
                user_id,
                "⚠️ Daily digest failed. Check that your accounts are connected (/accounts).",
            )
        except Exception:
            logger.exception("Failed to notify user %d of digest error", user_id)
