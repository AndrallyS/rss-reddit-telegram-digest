"""Dataclasses shared across the project."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RSSFeedConfig:
    name: str
    url: str
    category: str
    limit: int = 10


@dataclass(slots=True)
class RedditEndpointConfig:
    name: str
    path: str
    enabled: bool
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SubredditConfig:
    name: str
    category: str
    limit: int = 15


@dataclass(slots=True)
class SourcesConfig:
    rss_feeds: list[RSSFeedConfig]
    reddit_subreddits: list[SubredditConfig]
    reddit_validation_subreddits: list[str]
    reddit_time_window_hours: int
    reddit_endpoints: list[RedditEndpointConfig]
    reddit_request_delay_seconds: float = 0.0
    reddit_max_items_per_category: int = 10
    reddit_max_requests_per_run: int = 20


@dataclass(slots=True)
class RankingConfig:
    recency_window_hours: int
    weights: dict[str, float]
    category_bonus: dict[str, float]
    section_limits: dict[str, int]
    telegram_message_limit: int
    section_order: list[str] = field(default_factory=list)
    section_titles: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    root_dir: Path
    output_dir: Path
    log_dir: Path
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    reddit_user_agent: str
    request_timeout_seconds: float
    enable_reddit: bool
    log_level: str
    max_retries: int
    backoff_base_seconds: float
    sent_history_window_hours: int


@dataclass(slots=True)
class ScoreSignals:
    recency_hours: float = 0.0
    reddit_score: int = 0
    num_comments: int = 0
    multi_source_count: int = 1
    duplicate_penalty: float = 0.0
    source_reliability_bonus: float = 0.0
    ranking_score: float = 0.0


@dataclass(slots=True)
class CollectedItem:
    source_type: str
    source_name: str
    category: str
    title: str
    canonical_url: str
    discussion_url: str | None
    published_at: datetime
    summary: str
    score_signals: ScoreSignals = field(default_factory=ScoreSignals)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    seen_in_sources: list[str] = field(default_factory=list)
    source_priority: int = 0


@dataclass(slots=True)
class FetchOutcome:
    source: str
    status: str
    items_collected: int = 0
    detail: str | None = None
    elapsed_ms: float | None = None
    endpoint: str | None = None
    status_code: int | None = None
    content_type: str | None = None


@dataclass(slots=True)
class SourceHealthRecord:
    source_name: str
    status: str = "unknown"
    consecutive_failures: int = 0
    last_error: str | None = None
    last_success_at: str | None = None


@dataclass(slots=True)
class TelegramSendResult:
    sent: bool
    delivered_messages: int
    detail: str


@dataclass(slots=True)
class RedditValidationCheck:
    subreddit: str
    endpoint: str
    url: str
    status_code: int | None
    content_type: str | None
    json_valid: bool
    posts_count: int
    missing_fields: list[str]
    elapsed_ms: float | None
    diagnosis: str
