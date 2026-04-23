"""Split sections into token-sized chunks using tiktoken.

Uses ``cl100k_base`` encoding (OpenAI / reasonable approximation for most LLMs).
Controlled by the ``DOC_CHUNK_SIZE`` env var (default 10 000 tokens).

If a section's text fits within the limit it is returned as-is.
Oversized sections are split on newlines to avoid cutting mid-sentence.
Each chunk inherits the section's number, title, and level.
"""

from __future__ import annotations

import os

import tiktoken

from doc_models import Section

_MAX_TOKENS = int(os.getenv("DOC_CHUNK_SIZE", "10000"))

_enc = tiktoken.get_encoding("cl100k_base")


def chunk_sections(sections: list[Section], max_tokens: int | None = None) -> list[Section]:
    """Return sections split into at most *max_tokens* tokens each (default: DOC_CHUNK_SIZE env)."""
    limit = max_tokens if max_tokens is not None else _MAX_TOKENS
    result: list[Section] = []
    for sec in sections:
        result.extend(_chunk_one(sec, limit))
    return result


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


# ---------------------------------------------------------------------------

def _chunk_one(sec: Section, max_tokens: int) -> list[Section]:
    tokens = _enc.encode(sec.text)
    if len(tokens) <= max_tokens:
        return [sec]

    lines = sec.text.split("\n")
    chunks: list[Section] = []
    current_lines: list[str] = []
    current_tokens = 0
    part = 1

    for line in lines:
        line_tokens = len(_enc.encode(line + "\n"))
        if current_tokens + line_tokens > max_tokens and current_lines:
            chunks.append(_make_chunk(sec, "\n".join(current_lines), part))
            part += 1
            current_lines = []
            current_tokens = 0
        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunks.append(_make_chunk(sec, "\n".join(current_lines), part))

    return chunks


def _make_chunk(sec: Section, text: str, part: int) -> Section:
    suffix = f" (часть {part})"
    return Section(
        number=sec.number,
        title=sec.title + suffix,
        text=text,
        level=sec.level,
    )
