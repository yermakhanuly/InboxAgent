# InboxAgent

A personal Telegram bot that aggregates your Gmail, Outlook, Google Calendar, and Teams meetings into a daily 8 AM digest. Ask it questions about your inbox or calendar any time of day.

## Features

- **Daily digest at 8 AM (London time)** — emails + calendar events summarised by Claude AI
- **On-demand commands** — `/digest`, `/inbox`, `/calendar`
- **Natural language queries** — "what meetings do I have tomorrow?" or "any emails from Alice?"
- **Multi-account support** — connect multiple Gmail and/or Outlook accounts
- **Encrypted token storage** — OAuth tokens stored AES-encrypted in SQLite

## Quick start

### 1. Prerequisites

- Python 3.12+
- A Telegram bot token ([create one via @BotFather](https://t.me/BotFather))
- Your numeric Telegram user ID (message @userinfobot)
- An Anthropic API key
- (Optional) Google Cloud project with Gmail + Calendar APIs enabled
- (Optional) Azure App Registration with Mail.Read + Calendars.Read scopes

### 2. Configure

```bash
cp .env.example .env
# Edit .env and fill in all required values

# Generate an encryption key for token storage:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

mkdir -p /data   # or set DATABASE_PATH to a local path in .env
python -m inboxagent.main
```

### 4. Run with Docker

```bash
docker compose up -d
```

## Bot commands

| Command | Description |
|---|---|
| `/start` | Welcome message + connect accounts |
| `/auth_google` | Connect Gmail + Google Calendar |
| `/auth_microsoft` | Connect Outlook + Teams Calendar |
| `/accounts` | View and manage connected accounts |
| `/digest` | Get your digest right now |
| `/inbox` | Show latest unread emails |
| `/calendar` | Show today's events |
| `/help` | Show all commands |

## Google OAuth setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable **Gmail API** and **Google Calendar API**
3. OAuth consent screen → External → Add your email as test user
4. Credentials → Create → **Desktop app**
5. Copy Client ID and Secret to `.env`

## Microsoft OAuth setup

1. Go to [portal.azure.com](https://portal.azure.com) → App registrations → New
2. Supported account types: **Accounts in any org + personal**
3. Redirect URI: `http://localhost:8080/callback/microsoft`
4. API permissions → Add: `Mail.Read`, `Calendars.Read`, `offline_access`, `User.Read`
5. Certificates & secrets → New client secret
6. Copy Application (client) ID and secret to `.env`

## Architecture

```
main.py               ← PTB bot + APScheduler in one process
config.py             ← pydantic-settings env loading
database.py           ← SQLite schema (aiosqlite)
auth/                 ← OAuth flows + encrypted token storage
providers/            ← Gmail, Google Calendar, Outlook, Teams via APIs
ai/summarizer.py      ← Claude claude-sonnet-4-6 with prompt caching
ai/agent.py           ← Interactive Claude agent with tool use
digest/builder.py     ← Concurrent asyncio.gather across all providers
scheduler/jobs.py     ← APScheduler CronTrigger at 08:00 Europe/London
```
