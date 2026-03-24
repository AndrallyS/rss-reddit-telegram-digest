from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.models import RedditEndpointConfig
from app.sources import reddit_json_fetcher as reddit_module


class FakeResponse:
    def __init__(self, *, status_code: int, headers: dict[str, str], text: str, payload=None):
        self.status_code = status_code
        self.headers = headers
        self.text = text
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_parse_reddit_listing_filters_stickied_and_old_posts(sample_reddit_payload):
    now = datetime.now(tz=UTC)
    sample_reddit_payload["data"]["children"].append(
        {
            "kind": "t3",
            "data": {
                "id": "old1",
                "title": "Old post",
                "created_utc": (now - timedelta(hours=30)).timestamp(),
                "score": 10,
                "num_comments": 2,
                "permalink": "/r/technology/comments/old1/old_post/",
                "subreddit": "technology",
                "url": "https://example.com/old",
                "domain": "example.com",
                "selftext": "",
                "stickied": False,
                "over_18": False,
            },
        }
    )
    sample_reddit_payload["data"]["children"].append(
        {
            "kind": "t3",
            "data": {
                "id": "sticky1",
                "title": "Pinned",
                "created_utc": (now - timedelta(hours=1)).timestamp(),
                "score": 30,
                "num_comments": 9,
                "permalink": "/r/technology/comments/sticky1/pinned/",
                "subreddit": "technology",
                "url": "https://example.com/pinned",
                "domain": "example.com",
                "selftext": "",
                "stickied": True,
                "over_18": False,
            },
        }
    )

    items, missing = reddit_module.parse_reddit_listing(
        payload=sample_reddit_payload,
        subreddit="technology",
        category="tech",
        endpoint_name="top_day",
        time_window_hours=24,
    )

    assert missing == []
    assert len(items) == 1
    assert items[0]["id"] == "abc123"


def test_validate_listing_payload_reports_missing_fields():
    payload = {"kind": "Listing", "data": {"children": [{"kind": "t3", "data": {"title": "x"}}]}}
    is_valid, missing, children, diagnosis = reddit_module.validate_listing_payload(payload)

    assert is_valid is True
    assert "id" in missing
    assert len(children) == 1
    assert diagnosis == "incomplete_payload"


def test_request_reddit_listing_rejects_invalid_content_type(monkeypatch, app_config):
    fake_response = FakeResponse(
        status_code=200,
        headers={"content-type": "text/plain"},
        text='{"kind":"Listing"}',
        payload={"kind": "Listing"},
    )

    monkeypatch.setattr(
        reddit_module,
        "request_with_retry",
        lambda **kwargs: (fake_response, 12.0),
    )

    payload, outcome = reddit_module.request_reddit_listing(
        app_config=app_config,
        subreddit="technology",
        endpoint=RedditEndpointConfig(name="new", path="new/.json", enabled=True, params={}),
        logger=logging.getLogger("test"),
        session=None,
    )

    assert payload is None
    assert outcome.status == "unexpected_content"
    assert outcome.detail == "invalid_content_type"


def test_request_reddit_listing_rejects_html_and_bad_json(monkeypatch, app_config):
    html_response = FakeResponse(
        status_code=200,
        headers={"content-type": "text/html"},
        text="<html>blocked</html>",
        payload={"kind": "Listing"},
    )
    monkeypatch.setattr(reddit_module, "request_with_retry", lambda **kwargs: (html_response, 10.0))
    payload, outcome = reddit_module.request_reddit_listing(
        app_config=app_config,
        subreddit="technology",
        endpoint=RedditEndpointConfig(name="new", path="new/.json", enabled=True, params={}),
        logger=logging.getLogger("test"),
        session=None,
    )
    assert payload is None
    assert outcome.detail == "html_response"

    json_response = FakeResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        text="{",
        payload=ValueError("bad json"),
    )
    monkeypatch.setattr(reddit_module, "request_with_retry", lambda **kwargs: (json_response, 10.0))
    payload, outcome = reddit_module.request_reddit_listing(
        app_config=app_config,
        subreddit="technology",
        endpoint=RedditEndpointConfig(name="new", path="new/.json", enabled=True, params={}),
        logger=logging.getLogger("test"),
        session=None,
    )
    assert payload is None
    assert outcome.status == "invalid_json"
