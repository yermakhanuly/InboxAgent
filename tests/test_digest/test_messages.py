import pytest
from inboxagent.bot.messages import chunk_message, escape_markdown_v2


def test_chunk_short_message():
    text = "Hello world"
    assert chunk_message(text) == [text]


def test_chunk_exact_limit():
    text = "x" * 4096
    chunks = chunk_message(text)
    assert len(chunks) == 1
    assert len(chunks[0]) == 4096


def test_chunk_splits_on_paragraph_boundary():
    para1 = "First paragraph " + "a" * 100
    para2 = "Second paragraph " + "b" * 100
    # Create a text that requires splitting
    long_para1 = "a" * 3000
    long_para2 = "b" * 2000
    text = long_para1 + "\n\n" + long_para2
    chunks = chunk_message(text)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)
    assert long_para1 in chunks[0]
    assert long_para2 in chunks[1]


def test_chunk_rejoins_short_paragraphs():
    # Multiple short paragraphs that fit in one message
    text = "Para 1\n\nPara 2\n\nPara 3"
    chunks = chunk_message(text)
    assert len(chunks) == 1


def test_escape_markdown_v2():
    text = "Hello (world) - test!"
    escaped = escape_markdown_v2(text)
    assert "\\(" in escaped
    assert "\\)" in escaped
    assert "\\-" in escaped
    assert "\\!" in escaped
