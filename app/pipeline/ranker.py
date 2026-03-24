"""Transparent ranking for mixed RSS and Reddit items."""

from __future__ import annotations

from copy import deepcopy

from app.models import CollectedItem, RankingConfig
from app.utils import age_in_hours, log1p_scaled, utcnow


def score_item(item: CollectedItem, ranking_config: RankingConfig) -> float:
    now = utcnow()
    age_hours = age_in_hours(item.published_at, now=now)
    item.score_signals.recency_hours = age_hours

    weights = ranking_config.weights
    recency_window = max(float(ranking_config.recency_window_hours), 1.0)
    recency_score = max(0.0, 1 - min(age_hours, recency_window) / recency_window)
    reddit_score = (
        item.score_signals.reddit_score
        or item.raw_metadata.get("reddit", {}).get("score", 0)
    )
    comment_score = (
        item.score_signals.num_comments
        or item.raw_metadata.get("reddit", {}).get("num_comments", 0)
    )
    multi_source_count = max(item.score_signals.multi_source_count, len(item.seen_in_sources) or 1)
    reliability_bonus = (
        1.0 if "rss" in item.raw_metadata else 0.4 if item.source_type == "reddit" else 0.0
    )
    category_bonus = ranking_config.category_bonus.get(item.category, 0.0)

    total = (
        weights.get("recency", 0.0) * recency_score
        + weights.get("reddit_score", 0.0) * log1p_scaled(reddit_score)
        + weights.get("comments", 0.0) * log1p_scaled(comment_score)
        + weights.get("multi_source", 0.0) * max(multi_source_count - 1, 0)
        + weights.get("reliability", 0.0) * reliability_bonus
        + category_bonus
        - weights.get("duplicate_penalty", 0.0) * item.score_signals.duplicate_penalty
    )
    item.score_signals.source_reliability_bonus = reliability_bonus
    item.score_signals.multi_source_count = multi_source_count
    item.score_signals.ranking_score = round(total, 4)
    item.raw_metadata["ranking"] = {
        "age_hours": round(age_hours, 2),
        "reddit_score": reddit_score,
        "num_comments": comment_score,
        "multi_source_count": multi_source_count,
        "reliability_bonus": reliability_bonus,
        "category_bonus": category_bonus,
        "score": round(total, 4),
    }
    return total


def rank_items(items: list[CollectedItem], ranking_config: RankingConfig) -> list[CollectedItem]:
    scored: list[CollectedItem] = []
    for item in items:
        cloned = deepcopy(item)
        score_item(cloned, ranking_config)
        scored.append(cloned)
    return sorted(scored, key=lambda item: item.score_signals.ranking_score, reverse=True)
