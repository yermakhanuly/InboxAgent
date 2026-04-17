import re

TELEGRAM_MAX_LENGTH = 4096


def chunk_message(text: str) -> list[str]:
    """Split a message at paragraph boundaries, never exceeding Telegram's 4096-char limit."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        candidate = (current + "\n\n" + para).lstrip("\n") if current else para
        if len(candidate) <= TELEGRAM_MAX_LENGTH:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > TELEGRAM_MAX_LENGTH:
                # Split on single newlines as fallback
                lines = para.split("\n")
                current = ""
                for line in lines:
                    if len(current) + len(line) + 1 <= TELEGRAM_MAX_LENGTH:
                        current = (current + "\n" + line).lstrip("\n")
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = line[:TELEGRAM_MAX_LENGTH]
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:TELEGRAM_MAX_LENGTH]]


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(r"([" + re.escape(special) + r"])", r"\\\1", text)
