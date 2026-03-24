from __future__ import annotations

from app.pipeline.ranker import rank_items


def test_ranker_prefers_recent_and_high_signal_items(make_item, ranking_config):
    older = make_item(source_type="rss", title="Older", url="https://example.com/older", hours_ago=10)
    hotter = make_item(
        source_type="reddit",
        title="Hot",
        url="https://example.com/hot",
        hours_ago=1,
        reddit_score=2000,
        num_comments=300,
    )

    ranked = rank_items([older, hotter], ranking_config)

    assert ranked[0].title == "Hot"
    assert ranked[0].score_signals.ranking_score >= ranked[1].score_signals.ranking_score


def test_ranker_handles_mixed_rss_and_reddit(make_item, ranking_config):
    rss_item = make_item(source_type="rss", title="Reliable", url="https://example.com/reliable", hours_ago=2)
    mixed_item = make_item(
        source_type="rss",
        title="Shared",
        url="https://example.com/shared",
        hours_ago=3,
        reddit_score=500,
        num_comments=80,
        seen_in_sources=["rss", "r/technology"],
    )
    mixed_item.raw_metadata["reddit"] = {"score": 500, "num_comments": 80}

    ranked = rank_items([rss_item, mixed_item], ranking_config)

    assert ranked[0].title == "Shared"
    assert ranked[0].raw_metadata["ranking"]["multi_source_count"] == 2

