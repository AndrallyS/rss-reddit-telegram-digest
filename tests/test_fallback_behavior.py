from __future__ import annotations

import json
import logging

from app.health import HealthTracker
from app.models import FetchOutcome, RedditEndpointConfig, SubredditConfig, TelegramSendResult
from app.pipeline.runner import run_digest
from app.sources import reddit_json_fetcher as reddit_module
from app.utils import save_json


def test_digest_keeps_rss_when_reddit_disabled(app_config, sources_config, ranking_config):
    def fake_rss_fetcher(**kwargs):
        return (
            [
                {
                    "source": "Feed",
                    "source_type": "rss",
                    "category": "tech",
                    "title": "RSS item",
                    "url": "https://example.com/rss",
                    "published_at": "2026-03-23T10:00:00+00:00",
                    "summary": "rss summary",
                }
            ],
            [FetchOutcome(source="Feed", status="ok", items_collected=1)],
        )

    report = run_digest(
        app_config=app_config,
        sources_config=sources_config,
        ranking_config=ranking_config,
        logger=logging.getLogger("test"),
        rss_fetcher=fake_rss_fetcher,
        telegram_sender=lambda **kwargs: TelegramSendResult(False, 0, "skipped"),
    )

    assert report["rss_items"] == 1
    assert report["reddit_items"] == 0
    assert report["reddit_policy"]["enabled"] is False
    assert (app_config.output_dir / "ranked_items.json").exists()
    assert report["history_dir"] is not None


def test_digest_falls_back_when_reddit_enabled_but_fetch_returns_empty(
    app_config,
    sources_config,
    ranking_config,
):
    app_config.enable_reddit = True
    save_json(
        app_config.output_dir / "reddit_validation_report.json",
        {
            "recommendations": {"enable_reddit_optionally": True},
            "summary": {"classification": "functional_but_unstable"},
        },
    )

    def fake_rss_fetcher(**kwargs):
        return (
            [
                {
                    "source": "Feed",
                    "source_type": "rss",
                    "category": "tech",
                    "title": "RSS survives",
                    "url": "https://example.com/rss",
                    "published_at": "2026-03-23T10:00:00+00:00",
                    "summary": "rss summary",
                }
            ],
            [FetchOutcome(source="Feed", status="ok", items_collected=1)],
        )

    def fake_reddit_fetcher(**kwargs):
        return ([], [FetchOutcome(source="r/technology", status="http_error", detail="http_403")])

    report = run_digest(
        app_config=app_config,
        sources_config=sources_config,
        ranking_config=ranking_config,
        logger=logging.getLogger("test"),
        rss_fetcher=fake_rss_fetcher,
        reddit_fetcher=fake_reddit_fetcher,
        telegram_sender=lambda **kwargs: TelegramSendResult(False, 0, "skipped"),
    )

    assert report["reddit_policy"]["enabled"] is True
    assert report["rss_items"] == 1
    assert report["reddit_items"] == 0
    ranked = json.loads((app_config.output_dir / "ranked_items.json").read_text(encoding="utf-8"))
    assert ranked[0]["title"] == "RSS survives"


def test_digest_dry_run_skips_telegram_and_saves_history(app_config, sources_config, ranking_config):
    def fake_rss_fetcher(**kwargs):
        return (
            [
                {
                    "source": "Feed",
                    "source_type": "rss",
                    "category": "tech",
                    "title": "RSS survives",
                    "url": "https://example.com/rss",
                    "published_at": "2026-03-23T10:00:00+00:00",
                    "summary": "rss summary",
                }
            ],
            [FetchOutcome(source="Feed", status="ok", items_collected=1)],
        )

    called = {"telegram": False}

    def fake_telegram_sender(**kwargs):
        called["telegram"] = True
        return TelegramSendResult(True, 1, "should not run")

    report = run_digest(
        app_config=app_config,
        sources_config=sources_config,
        ranking_config=ranking_config,
        logger=logging.getLogger("test"),
        dry_run=True,
        rss_fetcher=fake_rss_fetcher,
        telegram_sender=fake_telegram_sender,
    )

    assert called["telegram"] is False
    assert report["dry_run"] is True
    assert report["telegram"]["detail"] == "Dry-run enabled. Telegram send skipped."
    assert report["history_dir"] is not None
    assert (app_config.output_dir / "history").exists()


def test_one_subreddit_failure_does_not_stop_others(app_config, sources_config, sample_reddit_payload, monkeypatch):
    outcomes = {
        "technology": (None, FetchOutcome(source="r/technology", status="http_error", detail="http_403", endpoint="top_day")),
        "games": (sample_reddit_payload, FetchOutcome(source="r/games", status="ok", endpoint="top_day")),
    }

    def fake_request(**kwargs):
        subreddit = kwargs["subreddit"]
        return outcomes[subreddit]

    monkeypatch.setattr(reddit_module, "request_reddit_listing", fake_request)
    items, fetch_outcomes = reddit_module.fetch_reddit_items(
        app_config=app_config,
        subreddits=sources_config.reddit_subreddits,
        endpoints=[sources_config.reddit_endpoints[0]],
        time_window_hours=24,
        request_delay_seconds=0.0,
        max_items_per_category=10,
        max_requests_per_run=10,
        logger=logging.getLogger("test"),
        health_tracker=HealthTracker(),
    )

    assert len(items) == 1
    assert any(outcome.source == "r/technology" for outcome in fetch_outcomes)
    assert any(outcome.source == "r/games" for outcome in fetch_outcomes)


def test_reddit_fetch_stops_after_category_target(app_config, monkeypatch):
    payload = {
        "kind": "Listing",
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "abc123",
                        "title": "First",
                        "created_utc": 1774336800,
                        "score": 100,
                        "num_comments": 12,
                        "permalink": "/r/technology/comments/abc123/first/",
                        "subreddit": "technology",
                        "url": "https://www.reddit.com/r/technology/comments/abc123/first/",
                        "domain": "reddit.com",
                        "selftext": "one",
                        "stickied": False,
                        "over_18": False,
                    },
                },
                {
                    "kind": "t3",
                    "data": {
                        "id": "def456",
                        "title": "Second",
                        "created_utc": 1774336800,
                        "score": 90,
                        "num_comments": 8,
                        "permalink": "/r/technology/comments/def456/second/",
                        "subreddit": "technology",
                        "url": "https://www.reddit.com/r/technology/comments/def456/second/",
                        "domain": "reddit.com",
                        "selftext": "two",
                        "stickied": False,
                        "over_18": False,
                    },
                },
            ]
        },
    }
    requested_subreddits: list[str] = []

    def fake_request(**kwargs):
        requested_subreddits.append(kwargs["subreddit"])
        return payload, FetchOutcome(
            source=f"r/{kwargs['subreddit']}",
            status="ok",
            endpoint=kwargs["endpoint"].name,
        )

    monkeypatch.setattr(reddit_module, "request_reddit_listing", fake_request)

    items, _ = reddit_module.fetch_reddit_items(
        app_config=app_config,
        subreddits=[
            SubredditConfig(name="technology", category="tech", limit=8),
            SubredditConfig(name="programming", category="tech", limit=8),
        ],
        endpoints=[RedditEndpointConfig(name="top_day", path="top/.json", enabled=True)],
        time_window_hours=24,
        request_delay_seconds=0.0,
        max_items_per_category=2,
        max_requests_per_run=10,
        logger=logging.getLogger("test"),
        health_tracker=HealthTracker(),
    )

    assert len(items) == 2
    assert requested_subreddits == ["technology"]
