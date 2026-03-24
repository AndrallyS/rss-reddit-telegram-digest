"""Short text summarization helpers."""

from __future__ import annotations

from app.utils import clean_text, truncate_text


def summarize(value: str | None, max_length: int = 180) -> str:
    return truncate_text(clean_text(value), max_length)

