from __future__ import annotations

from app.pipeline.formatter import format_digest_messages


def test_formatter_builds_sections(make_item, ranking_config):
    items = [
        make_item(source_type="rss", title="Tech RSS", url="https://example.com/tech", category="tech"),
        make_item(
            source_type="reddit",
            title="Games Reddit",
            url="https://www.reddit.com/r/games/comments/abc123/thread/",
            category="games",
            reddit_score=50,
        ),
        make_item(source_type="rss", title="AI RSS", url="https://example.com/ai", category="ai"),
    ]
    items[1].raw_metadata["reddit"] = {"score": 50, "num_comments": 10}
    items[1].source_name = "r/games"

    messages = format_digest_messages(items, ranking_config)

    combined = "\n".join(messages)
    assert "GAMES" in combined
    assert "TECH" in combined
    assert "IA" in combined
    assert "My Daily Briefing" in combined
    assert "50 up" in combined


def test_formatter_does_not_repeat_same_item_across_sections(make_item, ranking_config):
    repeated = make_item(
        source_type="rss",
        title="Shared Item",
        url="https://example.com/shared",
        category="tech",
    )
    repeated.raw_metadata["reddit"] = {"score": 250, "num_comments": 20}
    repeated.source_name = "Ars Technica"

    messages = format_digest_messages([repeated], ranking_config)

    combined = "\n".join(messages)
    assert combined.count("https://example.com/shared") == 1


def test_formatter_hides_reddit_metrics_for_external_link(make_item, ranking_config):
    item = make_item(
        source_type="rss",
        title="Tech Article",
        url="https://example.com/article",
        category="tech",
        reddit_score=358,
        num_comments=22,
    )
    item.raw_metadata["reddit"] = {"score": 358, "num_comments": 22}
    item.source_name = "TechCrunch"
    item.discussion_url = "https://www.reddit.com/r/technology/comments/abc123/thread/"

    messages = format_digest_messages([item], ranking_config)

    combined = "\n".join(messages)
    assert "358 up" not in combined
    assert "22 comments" not in combined
    assert "Reddit thread:" in combined


def test_formatter_marks_reddit_primary_link_clearly(make_item, ranking_config):
    item = make_item(
        source_type="reddit",
        title="Discussion Thread",
        url="https://www.reddit.com/r/technology/comments/abc123/thread/",
        category="tech",
        reddit_score=500,
        num_comments=44,
    )
    item.raw_metadata["reddit"] = {"score": 500, "num_comments": 44}
    item.source_name = "r/technology"

    messages = format_digest_messages([item], ranking_config)

    combined = "\n".join(messages)
    assert "[Reddit] Discussion Thread" in combined
    assert "Source: Reddit /r/technology" in combined
    assert "500 up" in combined
    assert "44 comments" in combined


def test_formatter_splits_large_messages(make_item, ranking_config):
    ranking_config.telegram_message_limit = 250
    items = [
        make_item(source_type="rss", title=f"Item {index}", url=f"https://example.com/{index}", category="tech")
        for index in range(10)
    ]

    messages = format_digest_messages(items, ranking_config)

    assert len(messages) > 1
