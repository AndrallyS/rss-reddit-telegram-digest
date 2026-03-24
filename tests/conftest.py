from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models import (
    AppConfig,
    CollectedItem,
    RankingConfig,
    RSSFeedConfig,
    RedditEndpointConfig,
    ScoreSignals,
    SourcesConfig,
    SubredditConfig,
)


@pytest.fixture()
def app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        root_dir=tmp_path,
        output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        telegram_bot_token=None,
        telegram_chat_id=None,
        reddit_user_agent="tests/1.0",
        request_timeout_seconds=1.0,
        enable_reddit=False,
        log_level="INFO",
        max_retries=0,
        backoff_base_seconds=0.01,
    )


@pytest.fixture()
def sources_config() -> SourcesConfig:
    return SourcesConfig(
        rss_feeds=[RSSFeedConfig(name="Feed", url="https://example.com/rss", category="tech", limit=10)],
        reddit_subreddits=[
            SubredditConfig(name="technology", category="tech", limit=10),
            SubredditConfig(name="games", category="games", limit=10),
        ],
        reddit_validation_subreddits=["technology", "games"],
        reddit_time_window_hours=24,
        reddit_endpoints=[
            RedditEndpointConfig(name="top_day", path="top/.json", enabled=True, params={"limit": 15, "t": "day"}),
            RedditEndpointConfig(name="new", path="new/.json", enabled=True, params={"limit": 15}),
        ],
    )


@pytest.fixture()
def ranking_config() -> RankingConfig:
    return RankingConfig(
        recency_window_hours=24,
        weights={
            "recency": 3.5,
            "reddit_score": 0.65,
            "comments": 0.45,
            "multi_source": 1.2,
            "reliability": 1.1,
            "duplicate_penalty": 0.9,
        },
        category_bonus={"games": 0.15, "tech": 0.15},
        section_limits={"games": 4, "tech": 4, "reddit": 4, "rss": 4},
        telegram_message_limit=500,
        section_order=["games", "gamedev", "ai", "finance", "tech", "reddit", "rss"],
        section_titles={
            "games": "Games",
            "gamedev": "Game Dev",
            "ai": "IA",
            "finance": "Mercado",
            "tech": "Tech",
            "reddit": "Radar Reddit",
            "rss": "Cobertura Editorial",
        },
    )


@pytest.fixture()
def sample_reddit_payload() -> dict[str, object]:
    now = datetime.now(tz=UTC)
    return {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "abc123",
                        "title": "Valve updates Steam Deck software",
                        "created_utc": (now - timedelta(hours=2)).timestamp(),
                        "score": 1200,
                        "num_comments": 140,
                        "permalink": "/r/technology/comments/abc123/valve_updates_steam_deck_software/",
                        "subreddit": "technology",
                        "url": "https://www.theverge.com/example",
                        "domain": "theverge.com",
                        "selftext": "",
                        "stickied": False,
                        "over_18": False,
                    },
                }
            ]
        },
    }


@pytest.fixture()
def make_item():
    def _make_item(
        *,
        source_type: str,
        title: str,
        url: str,
        category: str = "tech",
        hours_ago: int = 1,
        reddit_score: int = 0,
        num_comments: int = 0,
        seen_in_sources: list[str] | None = None,
    ) -> CollectedItem:
        return CollectedItem(
            source_type=source_type,
            source_name="source",
            category=category,
            title=title,
            canonical_url=url,
            discussion_url=None,
            published_at=datetime.now(tz=UTC) - timedelta(hours=hours_ago),
            summary="summary",
            score_signals=ScoreSignals(
                reddit_score=reddit_score,
                num_comments=num_comments,
                multi_source_count=len(seen_in_sources or [source_type]),
            ),
            raw_metadata={
                source_type: {
                    "score": reddit_score,
                    "num_comments": num_comments,
                }
            },
            seen_in_sources=seen_in_sources or [source_type],
            source_priority=2 if source_type == "rss" else 1,
        )

    return _make_item
