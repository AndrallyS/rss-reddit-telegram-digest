from __future__ import annotations

from app.models import RedditValidationCheck
from app.sources.reddit_json_fetcher import summarize_validation_checks


def test_summarize_validation_checks_marks_blocked():
    checks = [
        RedditValidationCheck(
            subreddit="games",
            endpoint="top_day",
            url="https://reddit.test",
            status_code=403,
            content_type=None,
            json_valid=False,
            posts_count=0,
            missing_fields=[],
            elapsed_ms=100.0,
            diagnosis="http_403",
        ),
        RedditValidationCheck(
            subreddit="technology",
            endpoint="new",
            url="https://reddit.test",
            status_code=429,
            content_type=None,
            json_valid=False,
            posts_count=0,
            missing_fields=[],
            elapsed_ms=120.0,
            diagnosis="http_429",
        ),
    ]

    summary = summarize_validation_checks(checks)

    assert summary["classification"] == "blocked"
    assert summary["valid_json_checks"] == 0


def test_summarize_validation_checks_marks_functional_but_unstable():
    checks = [
        RedditValidationCheck(
            subreddit="games",
            endpoint="top_day",
            url="https://reddit.test",
            status_code=200,
            content_type="application/json",
            json_valid=True,
            posts_count=10,
            missing_fields=[],
            elapsed_ms=100.0,
            diagnosis="ok",
        ),
        RedditValidationCheck(
            subreddit="technology",
            endpoint="new",
            url="https://reddit.test",
            status_code=200,
            content_type="application/json",
            json_valid=True,
            posts_count=8,
            missing_fields=["score"],
            elapsed_ms=110.0,
            diagnosis="incomplete_payload",
        ),
    ]

    summary = summarize_validation_checks(checks)

    assert summary["classification"] == "functional_but_unstable"
    assert summary["incomplete_checks"] == 1
