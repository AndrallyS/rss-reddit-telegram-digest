"""Convert raw RSS and Reddit items into a common item model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models import CollectedItem
from app.pipeline.summarizer import summarize
from app.utils import canonicalize_url, parse_datetime


def normalize_rss_items(items: list[dict[str, Any]]) -> list[CollectedItem]:
    normalized: list[CollectedItem] = []
    for item in items:
        published_at = parse_datetime(item.get("published_at")) or datetime.now(tz=UTC)
        canonical_url = canonicalize_url(item.get("url"))
        if not item.get("title") or not canonical_url:
            continue
        normalized.append(
            CollectedItem(
                source_type="rss",
                source_name=item.get("source", "rss"),
                category=item.get("category", "general"),
                title=item["title"],
                canonical_url=canonical_url,
                discussion_url=None,
                published_at=published_at,
                summary=summarize(item.get("summary")),
                seen_in_sources=[item.get("source", "rss")],
                source_priority=2,
                raw_metadata={"rss": item},
            )
        )
    return normalized


def normalize_reddit_items(items: list[dict[str, Any]]) -> list[CollectedItem]:
    normalized: list[CollectedItem] = []
    for item in items:
        published_at = parse_datetime(item.get("created_utc")) or datetime.now(tz=UTC)
        canonical_url = canonicalize_url(item.get("external_url") or item.get("permalink"))
        if not item.get("title") or not canonical_url:
            continue
        normalized.append(
            CollectedItem(
                source_type="reddit",
                source_name=item.get("source", "reddit"),
                category=item.get("category", "general"),
                title=item["title"],
                canonical_url=canonical_url,
                discussion_url=item.get("permalink"),
                published_at=published_at,
                summary=summarize(item.get("summary")),
                seen_in_sources=[item.get("source", "reddit")],
                source_priority=1,
                raw_metadata={"reddit": item},
            )
        )
    return normalized


def normalize_all(
    rss_items: list[dict[str, Any]],
    reddit_items: list[dict[str, Any]],
) -> list[CollectedItem]:
    return normalize_rss_items(rss_items) + normalize_reddit_items(reddit_items)
