from __future__ import annotations

from app.pipeline.dedupe import deduplicate_items


def test_deduplicate_by_exact_url(make_item):
    rss_item = make_item(source_type="rss", title="Steam update", url="https://example.com/a")
    reddit_item = make_item(
        source_type="reddit",
        title="Steam update discussion",
        url="https://example.com/a",
        reddit_score=100,
        num_comments=20,
    )

    items, stats = deduplicate_items([rss_item, reddit_item])

    assert len(items) == 1
    assert stats["exact_url_merges"] == 1
    assert items[0].score_signals.reddit_score == 100
    assert "rss" in items[0].raw_metadata
    assert "reddit" in items[0].raw_metadata


def test_deduplicate_by_normalized_title(make_item):
    rss_item = make_item(source_type="rss", title="Valve launches update!", url="https://example.com/a")
    reddit_item = make_item(source_type="reddit", title="valve launches update", url="https://example.com/b")

    items, stats = deduplicate_items([rss_item, reddit_item])

    assert len(items) == 1
    assert stats["title_merges"] == 1


def test_deduplicate_by_similar_title(make_item):
    rss_item = make_item(
        source_type="rss",
        title="US regulator bans imports of new foreign-made routers, citing security concerns",
        url="https://example.com/reuters",
        category="tech",
    )
    reddit_item = make_item(
        source_type="reddit",
        title="US bans new foreign-made consumer internet routers",
        url="https://example.com/bbc",
        category="tech",
    )

    items, stats = deduplicate_items([rss_item, reddit_item])

    assert len(items) == 1
    assert stats["similar_title_merges"] == 1
