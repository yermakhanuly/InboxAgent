import asyncio
import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .config import settings
from .database import init_db

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    await init_db()
    logger.info("Database initialized")

    # Import here to avoid circular imports at module load time
    from .auth.http_server import OAuthCallbackServer
    from .scheduler.jobs import setup_scheduler

    server = OAuthCallbackServer(
        host=settings.oauth_callback_host,
        port=settings.oauth_callback_port,
    )
    await server.start()
    application.bot_data["oauth_server"] = server
    logger.info("OAuth callback server started on port %d", settings.oauth_callback_port)

    scheduler = setup_scheduler(application)
    scheduler.start()
    application.bot_data["scheduler"] = scheduler
    logger.info("Scheduler started")

    from .scheduler.jobs import schedule_digest
    await schedule_digest(application)


async def post_shutdown(application: Application) -> None:
    server = application.bot_data.get("oauth_server")
    if server:
        await server.stop()

    scheduler = application.bot_data.get("scheduler")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


def build_application() -> Application:
    from .bot.handlers import register_handlers

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    register_handlers(app)
    return app


def main() -> None:
    app = build_application()
    logger.info("InboxAgent starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
