"""RSS collection with defensive parsing and per-feed isolation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import feedparser
import requests

from app.models import AppConfig, FetchOutcome, RSSFeedConfig
from app.utils import clean_text, request_with_retry


def _entry_datetime(entry: Any) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        value = getattr(entry, attr, None)
        if value:
            return datetime(*value[:6], tzinfo=UTC)
    return None


def fetch_rss_items(
    *,
    app_config: AppConfig,
    feeds: list[RSSFeedConfig],
    logger: logging.Logger,
) -> tuple[list[dict[str, Any]], list[FetchOutcome]]:
    headers = {
        "User-Agent": app_config.reddit_user_agent,
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
    }
    session = requests.Session()
    raw_items: list[dict[str, Any]] = []
    outcomes: list[FetchOutcome] = []

    for feed in feeds:
        try:
            response, elapsed_ms = request_with_retry(
                session=session,
                url=feed.url,
                headers=headers,
                timeout=app_config.request_timeout_seconds,
                max_retries=app_config.max_retries,
                backoff_base_seconds=app_config.backoff_base_seconds,
                logger=logger,
            )
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError(str(parsed.bozo_exception))

            valid_count = 0
            for entry in parsed.entries[: feed.limit]:
                title = clean_text(getattr(entry, "title", ""))
                link = clean_text(getattr(entry, "link", ""))
                if not title or not link:
                    continue
                raw_items.append(
                    {
                        "source": feed.name,
                        "source_type": "rss",
                        "category": feed.category,
                        "title": title,
                        "url": link,
                        "published_at": _entry_datetime(entry),
                        "summary": clean_text(
                            getattr(entry, "summary", "") or getattr(entry, "description", "")
                        ),
                        "category_from_feed": clean_text(
                            getattr(entry, "category", "") or feed.category
                        ),
                        "raw": {
                            "feed_title": clean_text(
                                parsed.feed.get("title", "") if hasattr(parsed, "feed") else ""
                            ),
                            "entry_id": clean_text(getattr(entry, "id", "")),
                        },
                    }
                )
                valid_count += 1
            outcomes.append(
                FetchOutcome(
                    source=feed.name,
                    status="ok" if valid_count else "empty",
                    items_collected=valid_count,
                    elapsed_ms=elapsed_ms,
                )
            )
            logger.info("RSS feed processed: %s (%s items)", feed.name, valid_count)
        except requests.Timeout:
            detail = "timeout"
            outcomes.append(FetchOutcome(source=feed.name, status="timeout", detail=detail))
            logger.error("RSS timeout for %s", feed.name)
        except requests.HTTPError as exc:
            detail = f"http_error:{exc.response.status_code if exc.response else 'unknown'}"
            outcomes.append(FetchOutcome(source=feed.name, status="http_error", detail=detail))
            logger.error("RSS HTTP error for %s: %s", feed.name, detail)
        except requests.RequestException as exc:
            detail = f"network_error:{type(exc).__name__}"
            outcomes.append(FetchOutcome(source=feed.name, status="network_error", detail=detail))
            logger.error("RSS network error for %s: %s", feed.name, exc)
        except Exception as exc:  # noqa: BLE001
            detail = f"parse_error:{type(exc).__name__}"
            outcomes.append(FetchOutcome(source=feed.name, status="parse_error", detail=detail))
            logger.error("RSS parsing error for %s: %s", feed.name, exc)
    return raw_items, outcomes
