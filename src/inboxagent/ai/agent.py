"""Interactive agent for mid-day free-text queries via Telegram."""
import json
import logging
from datetime import datetime, timezone

import anthropic

from ..config import settings
from ..database import get_user_accounts

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are InboxAgent, a personal assistant with access to the user's email and calendar.
Answer their questions concisely using the available tools.
Be direct and helpful. If you cannot answer without data, call the appropriate tool first.
Format responses for Telegram — plain text, short, no unnecessary headers."""

TOOLS = [
    {
        "name": "get_emails",
        "description": "Fetch recent emails from Gmail and/or Outlook. Use this when the user asks about emails, messages, or inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional search query or filter (e.g. 'from:boss@company.com', 'subject:invoice'). Leave empty for all recent emails.",
                },
                "hours_back": {
                    "type": "integer",
                    "description": "How many hours back to look. Default 24.",
                    "default": 24,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_calendar_events",
        "description": "Fetch upcoming calendar events from Google Calendar and/or Teams. Use when user asks about meetings, schedule, or calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_description": {
                    "type": "string",
                    "description": "Natural language date range like 'today', 'tomorrow', 'this week', 'next Monday'.",
                    "default": "today",
                },
            },
            "required": [],
        },
    },
]


async def answer_query(user_id: int, question: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages = [{"role": "user", "content": question}]

    # Agentic loop — at most 3 tool-call rounds
    for _ in range(3):
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": AGENT_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _call_tool(user_id, block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return _extract_text(response)


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "I couldn't generate a response."


async def _call_tool(user_id: int, tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "get_emails":
            return await _tool_get_emails(user_id, tool_input)
        elif tool_name == "get_calendar_events":
            return await _tool_get_events(user_id, tool_input)
        return "Unknown tool"
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        return f"Error: {exc}"


async def _tool_get_emails(user_id: int, tool_input: dict) -> str:
    from ..digest.builder import fetch_emails_for_accounts

    accounts = await get_user_accounts(user_id)
    hours_back = tool_input.get("hours_back", 24)
    emails, errors = await fetch_emails_for_accounts(user_id, accounts, hours_back=hours_back)

    if not emails and not errors:
        return "No emails found."

    lines = []
    for email in emails[:15]:
        lines.append(
            f"[{email.account}] From: {email.sender} | Subject: {email.subject} | "
            f"Preview: {email.snippet[:300]}"
        )
    if errors:
        lines.extend(f"Error: {e}" for e in errors)
    return "\n".join(lines) or "No emails found."


async def _tool_get_events(user_id: int, tool_input: dict) -> str:
    from ..digest.builder import fetch_events_for_accounts

    accounts = await get_user_accounts(user_id)
    events, errors = await fetch_events_for_accounts(user_id, accounts)

    if not events and not errors:
        return "No events found."

    lines = []
    for event in sorted(events, key=lambda e: e.start_time):
        link = f" | Join: {event.meeting_url}" if event.meeting_url else ""
        lines.append(
            f"[{event.account}] {event.start_time.strftime('%H:%M')} {event.title}{link}"
        )
    if errors:
        lines.extend(f"Error: {e}" for e in errors)
    return "\n".join(lines) or "No events found."
