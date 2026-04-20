import asyncio
import logging
import secrets

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..config import settings
from ..database import ensure_user, get_user_accounts

logger = logging.getLogger(__name__)


def _authorized(user_id: int) -> bool:
    return user_id == settings.telegram_user_id


def _auth_check(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid is not None and _authorized(uid)


# ── /start ────────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id
    await ensure_user(user_id)

    from .keyboards import auth_menu_keyboard
    await update.effective_message.reply_text(
        "👋 Welcome to *InboxAgent*\\!\n\n"
        "I'll send you a daily digest at 8 AM with your emails and calendar events\\.\n\n"
        "Connect your accounts to get started:",
        parse_mode="MarkdownV2",
        reply_markup=auth_menu_keyboard(),
    )


# ── /auth_google ──────────────────────────────────────────────────────────────

async def auth_google_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id

    if not settings.google_client_id:
        await context.bot.send_message(user_id, "Google OAuth is not configured. Set GOOGLE_CLIENT_ID in .env")
        return

    server = context.bot_data["oauth_server"]
    state = secrets.token_urlsafe(16)
    future = server.register_state(state)

    from ..auth.google import get_google_auth_url
    auth_url, code_verifier = get_google_auth_url(state)

    await context.bot.send_message(
        user_id,
        f"Click to authenticate with Google:\n{auth_url}\n\nThis link expires in 5 minutes."
    )

    asyncio.create_task(
        _complete_google_auth(user_id, future, state, server, context, code_verifier)
    )


async def _complete_google_auth(
    user_id: int,
    future: asyncio.Future,
    state: str,
    server,
    context: ContextTypes.DEFAULT_TYPE,
    code_verifier: str | None = None,
) -> None:
    try:
        code = await asyncio.wait_for(future, timeout=settings.oauth_state_timeout_seconds)
        from ..auth.google import exchange_google_code, get_google_account_email
        from ..auth.token_store import token_store
        tokens = await exchange_google_code(code, code_verifier)
        email = await get_google_account_email(tokens)
        await token_store.save_token(user_id, "google", email, tokens)
        await context.bot.send_message(user_id, f"✅ Google account connected: {email}")
        logger.info("Google auth completed for user %d (%s)", user_id, email)
    except asyncio.TimeoutError:
        server.cancel_state(state)
        await context.bot.send_message(user_id, "⏰ Auth timed out. Use /auth_google to try again.")
    except Exception as exc:
        logger.exception("Google auth failed for user %d", user_id)
        await context.bot.send_message(user_id, f"❌ Google auth failed: {exc}")


# ── /auth_microsoft ───────────────────────────────────────────────────────────

async def auth_microsoft_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id

    if not settings.microsoft_client_id:
        await context.bot.send_message(user_id, "Microsoft OAuth is not configured. Set MICROSOFT_CLIENT_ID in .env")
        return

    server = context.bot_data["oauth_server"]
    state = secrets.token_urlsafe(16)
    future = server.register_state(state)

    from ..auth.microsoft import get_microsoft_direct_auth_url
    auth_url = get_microsoft_direct_auth_url(state)

    await context.bot.send_message(
        user_id,
        f"Click to authenticate with Microsoft:\n{auth_url}\n\nThis link expires in 5 minutes."
    )

    asyncio.create_task(
        _complete_microsoft_auth(user_id, future, state, server, context)
    )


async def _complete_microsoft_auth(
    user_id: int,
    future: asyncio.Future,
    state: str,
    server,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    try:
        code = await asyncio.wait_for(future, timeout=settings.oauth_state_timeout_seconds)
        from ..auth.microsoft import exchange_microsoft_code, get_microsoft_account_email
        from ..auth.token_store import token_store
        tokens = await exchange_microsoft_code(code, state)
        email = await get_microsoft_account_email(tokens)
        await token_store.save_token(user_id, "microsoft", email, tokens)
        await context.bot.send_message(user_id, f"✅ Microsoft account connected: {email}")
        logger.info("Microsoft auth completed for user %d (%s)", user_id, email)
    except asyncio.TimeoutError:
        server.cancel_state(state)
        await context.bot.send_message(user_id, "⏰ Auth timed out. Use /auth_microsoft to try again.")
    except Exception as exc:
        logger.exception("Microsoft auth failed for user %d", user_id)
        await context.bot.send_message(user_id, f"❌ Microsoft auth failed: {exc}")


# ── /accounts ─────────────────────────────────────────────────────────────────

async def accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id
    accounts = await get_user_accounts(user_id)

    if not accounts:
        await update.effective_message.reply_text(
            "No accounts connected. Use /auth_google or /auth_microsoft."
        )
        return

    from .keyboards import connected_accounts_keyboard
    lines = "\n".join(f"• {'Google' if p == 'google' else 'Microsoft'}: {e}" for p, e in accounts)
    await update.effective_message.reply_text(
        f"Connected accounts:\n{lines}",
        reply_markup=connected_accounts_keyboard(accounts),
    )


# ── /digest ───────────────────────────────────────────────────────────────────

async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id
    await update.effective_message.reply_text("📬 Generating your digest...")
    await update.effective_chat.send_action(ChatAction.TYPING)

    from ..scheduler.jobs import send_daily_digest
    await send_daily_digest(user_id, context.application)


# ── /inbox ────────────────────────────────────────────────────────────────────

async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id
    await update.effective_chat.send_action(ChatAction.TYPING)

    from ..digest.builder import fetch_emails_only
    from .messages import chunk_message

    try:
        result = await fetch_emails_only(user_id)
        if not result:
            await update.effective_message.reply_text("No unread emails found.")
            return
        for chunk in chunk_message(result):
            await update.effective_message.reply_text(chunk)
    except Exception as exc:
        await update.effective_message.reply_text(f"❌ Error fetching inbox: {exc}")


# ── /calendar ─────────────────────────────────────────────────────────────────

async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id
    await update.effective_chat.send_action(ChatAction.TYPING)

    from ..digest.builder import fetch_events_only
    from .messages import chunk_message

    try:
        result = await fetch_events_only(user_id)
        if not result:
            await update.effective_message.reply_text("No upcoming events found.")
            return
        for chunk in chunk_message(result):
            await update.effective_message.reply_text(chunk)
    except Exception as exc:
        await update.effective_message.reply_text(f"❌ Error fetching calendar: {exc}")


# ── /help ─────────────────────────────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    await update.effective_message.reply_text(
        "/start — Welcome & connect accounts\n"
        "/auth_google — Connect Gmail + Google Calendar\n"
        "/auth_microsoft — Connect Outlook + Teams Calendar\n"
        "/accounts — Manage connected accounts\n"
        "/digest — Get your digest now\n"
        "/inbox — Show latest emails\n"
        "/calendar — Show today's events\n"
        "/help — Show this message\n\n"
        "You can also ask me anything about your inbox or calendar in plain text."
    )


# ── Free-text agent ───────────────────────────────────────────────────────────

async def free_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _auth_check(update):
        return

    user_id = update.effective_user.id
    text = update.message.text or ""
    await update.effective_chat.send_action(ChatAction.TYPING)

    from ..ai.agent import answer_query
    from .messages import chunk_message

    try:
        reply = await answer_query(user_id, text)
        for chunk in chunk_message(reply):
            await update.effective_message.reply_text(chunk)
    except Exception as exc:
        logger.exception("Free-text agent error for user %d", user_id)
        await update.effective_message.reply_text(f"❌ Error: {exc}")


# ── Callback query (inline keyboard buttons) ──────────────────────────────────

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "auth_google":
        await auth_google_command(update, context)
    elif data == "auth_microsoft":
        await auth_microsoft_command(update, context)
    elif data == "add_account":
        from .keyboards import auth_menu_keyboard
        await query.message.reply_text("Which account would you like to add?", reply_markup=auth_menu_keyboard())
    elif data and data.startswith("remove_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            _, provider, email = parts
            from ..auth.token_store import token_store
            user_id = update.effective_user.id
            await token_store.delete_token(user_id, provider, email)
            await query.message.reply_text(f"✅ Removed {provider} account: {email}")


# ── Registration ──────────────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("auth_google", auth_google_command))
    app.add_handler(CommandHandler("auth_microsoft", auth_microsoft_command))
    app.add_handler(CommandHandler("accounts", accounts_command))
    app.add_handler(CommandHandler("digest", digest_command))
    app.add_handler(CommandHandler("inbox", inbox_command))
    app.add_handler(CommandHandler("calendar", calendar_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_text_handler))
