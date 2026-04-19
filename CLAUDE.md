# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable with dev extras)
pip install -e ".[dev]"

# Run the bot
python -m inboxagent.main

# Run all tests
pytest

# Run a single test file
pytest tests/test_ai/test_summarizer.py

# Run a single test
pytest tests/test_ai/test_summarizer.py::test_build_prompt_includes_emails

# Syntax check all Python files
python -m py_compile $(find src tests -name "*.py")
```

No lint or type-check tooling is currently configured.

## Environment setup

Copy `.env.example` to `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_USER_ID` (get ID from @userinfobot in Telegram)
- `OPENAI_API_KEY`
- `TOKEN_ENCRYPTION_KEY` — generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Google and Microsoft OAuth credentials (optional — bot works without them)

## Architecture

The bot is a single-user Telegram agent. `TELEGRAM_USER_ID` is hardcoded as the only authorized user — all handlers silently drop messages from anyone else via `_authorized()` in [handlers.py](src/inboxagent/bot/handlers.py).

### Startup sequence (`main.py`)

`Application.run_polling()` → PTB calls `post_init()` which:
1. Initializes SQLite DB
2. Starts the aiohttp OAuth callback server on `localhost:8080`
3. Starts APScheduler and registers the 8 AM digest cron job

Everything runs in a single `asyncio` event loop managed by python-telegram-bot.

### Data flow for the daily digest

```
scheduler/jobs.py (cron 08:00 Europe/London)
  → digest/builder.py build_digest()
      → asyncio.gather(fetch_emails_for_accounts, fetch_events_for_accounts)
          each provider wrapped in asyncio.wait_for(..., timeout=10.0)
          each provider call decorated with @with_retry (exponential backoff)
      → ai/summarizer.py summarize_digest()  [GPT-4o]
  → bot sends chunked messages to TELEGRAM_USER_ID
```

### Data flow for free-text queries

Any non-command message → `free_text_handler` → `ai/agent.py answer_query()` — an agentic loop (max 3 rounds) with two tools: `get_emails` and `get_calendar_events`. These tools call back into `digest/builder.py`. Tool definitions use OpenAI's `{"type": "function", "function": {...}}` format.

### OAuth flow

Both Google and Microsoft use the same pattern in `bot/handlers.py`:
1. Register a random `state` token with `OAuthCallbackServer.register_state(state)` — this creates an `asyncio.Future`
2. Send the auth URL to the user
3. `asyncio.create_task(_complete_*_auth(...))` awaits the future with a 300s timeout
4. aiohttp `OAuthCallbackServer` resolves the future when the redirect lands on `/callback/{provider}`
5. Tokens are encrypted (Fernet/AES) and stored in SQLite via `TokenStore`

Microsoft OAuth calls the token endpoint directly with `httpx` (not MSAL's flow object) to keep things simpler.

### Token lifecycle

`token_store.get_valid_token()` — called by every provider fetch — auto-refreshes tokens 5 minutes before expiry. If refresh fails it raises `TokenExpiredError`, which `with_retry` does **not** retry; it surfaces to the user as a re-auth prompt. `NoTokensError` is raised when no tokens exist at all.

Google API calls run inside `run_in_executor` because the Google client SDK is synchronous.

### Key invariants

- **Email snippets are capped at 500 chars** in `_build_prompt()` — full bodies never reach the AI or logs.
- **Provider failures are isolated**: `asyncio.gather(return_exceptions=True)` means one failing provider never crashes the digest; errors become `⚠️` notes in the summary.
- **Telegram 4096-char limit**: all outgoing text goes through `bot/messages.py chunk_message()` which splits on paragraph → line boundaries.
- **Scheduler misfire grace**: `misfire_grace_time=300` means the digest fires up to 5 min late after a restart; `coalesce=True` prevents duplicate firings.
- The `account` field on `EmailMessage` and `CalendarEvent` is a namespaced string like `"gmail:user@example.com"` or `"gcal:user@example.com"`.

## Package structure

```
src/inboxagent/
  config.py          — pydantic-settings Settings singleton
  database.py        — SQLite schema, init_db(), get_user_accounts()
  main.py            — entry point, PTB Application wiring
  auth/              — OAuth flows (google.py, microsoft.py), token_store.py, http_server.py
  bot/               — handlers.py, messages.py, keyboards.py
  providers/         — base.py (dataclasses + with_retry), gmail.py, outlook.py, google_calendar.py, teams_calendar.py
  ai/                — summarizer.py (digest → GPT-4o), agent.py (agentic loop)
  digest/            — builder.py (orchestrates providers), formatter.py (plain-text fallback)
  scheduler/         — jobs.py (APScheduler setup + cron job)
```

## Docker

```bash
docker compose up -d        # build + run
docker compose logs -f      # follow logs
```

Data is persisted in the `inbox_data` Docker volume mounted at `/data`.
