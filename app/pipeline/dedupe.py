"""Deduplicate exact and near-duplicate items while preserving useful signals."""

from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher

from app.models import CollectedItem
from app.utils import canonicalize_url, normalize_title

TITLE_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "after",
    "amid",
    "about",
    "just",
    "new",
}


def _merge_items(primary: CollectedItem, incoming: CollectedItem) -> CollectedItem:
    merged = deepcopy(primary)
    merged.summary = primary.summary or incoming.summary
    merged.discussion_url = primary.discussion_url or incoming.discussion_url
    merged.published_at = min(primary.published_at, incoming.published_at)
    merged.seen_in_sources = sorted(
        set(primary.seen_in_sources + incoming.seen_in_sources + [primary.source_name, incoming.source_name])
    )
    merged.score_signals.reddit_score = max(
        primary.score_signals.reddit_score,
        incoming.score_signals.reddit_score,
        incoming.raw_metadata.get("reddit", {}).get("score", 0),
        primary.raw_metadata.get("reddit", {}).get("score", 0),
    )
    merged.score_signals.num_comments = max(
        primary.score_signals.num_comments,
        incoming.score_signals.num_comments,
        incoming.raw_metadata.get("reddit", {}).get("num_comments", 0),
        primary.raw_metadata.get("reddit", {}).get("num_comments", 0),
    )
    merged.score_signals.multi_source_count = len(merged.seen_in_sources)
    merged.score_signals.duplicate_penalty += 0.1
    if primary.source_priority < incoming.source_priority:
        merged.source_type = incoming.source_type
        merged.source_name = incoming.source_name
    if "rss" in incoming.raw_metadata:
        merged.raw_metadata["rss"] = incoming.raw_metadata["rss"]
        merged.score_signals.source_reliability_bonus = max(
            merged.score_signals.source_reliability_bonus,
            0.2,
        )
    if "reddit" in incoming.raw_metadata:
        merged.raw_metadata["reddit"] = incoming.raw_metadata["reddit"]
    return merged


def _title_tokens(title: str) -> set[str]:
    return {
        token
        for token in normalize_title(title).split()
        if len(token) > 2 and token not in TITLE_STOPWORDS
    }


def _titles_similar(left: str, right: str) -> bool:
    left_normalized = normalize_title(left)
    right_normalized = normalize_title(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True

    left_tokens = _title_tokens(left)
    right_tokens = _title_tokens(right)
    if not left_tokens or not right_tokens:
        return False

    intersection = left_tokens & right_tokens
    union = left_tokens | right_tokens
    overlap = len(intersection) / min(len(left_tokens), len(right_tokens))
    jaccard = len(intersection) / len(union)
    ratio = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return (overlap >= 0.65 and jaccard >= 0.3) or ratio >= 0.82


def deduplicate_items(items: list[CollectedItem]) -> tuple[list[CollectedItem], dict[str, int]]:
    by_url: dict[str, CollectedItem] = {}
    by_title: dict[str, str] = {}
    stats = {
        "input_items": len(items),
        "exact_url_merges": 0,
        "title_merges": 0,
        "similar_title_merges": 0,
    }

    for item in items:
        url_key = canonicalize_url(item.canonical_url)
        title_key = normalize_title(item.title)
        if url_key and url_key in by_url:
            by_url[url_key] = _merge_items(by_url[url_key], item)
            stats["exact_url_merges"] += 1
            continue
        if title_key and title_key in by_title:
            existing_url_key = by_title[title_key]
            by_url[existing_url_key] = _merge_items(by_url[existing_url_key], item)
            stats["title_merges"] += 1
            continue

        similar_url_key = next(
            (
                existing_url_key
                for existing_url_key, existing_item in by_url.items()
                if existing_item.category == item.category
                and _titles_similar(existing_item.title, item.title)
            ),
            None,
        )
        if similar_url_key:
            by_url[similar_url_key] = _merge_items(by_url[similar_url_key], item)
            stats["similar_title_merges"] += 1
            continue

        if url_key:
            by_url[url_key] = item
            if title_key:
                by_title[title_key] = url_key

    return list(by_url.values()), stats
