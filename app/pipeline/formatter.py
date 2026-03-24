"""Telegram-friendly formatting with stronger section hierarchy and explicit Reddit links."""

from __future__ import annotations

import html
from datetime import UTC, datetime
from urllib.parse import urlsplit

from app.models import CollectedItem, RankingConfig
from app.utils import split_messages, truncate_text

SECTION_EMOJIS = {
    "games": "🎮",
    "gamedev": "🛠️",
    "ai": "🤖",
    "finance": "📈",
    "tech": "⚡",
    "reddit": "🔥",
    "rss": "📰",
}


def _item_key(item: CollectedItem) -> str:
    return item.canonical_url or item.discussion_url or item.title


def _is_reddit_url(url: str | None) -> bool:
    if not url:
        return False
    return "reddit.com" in urlsplit(url).netloc.lower()


def _is_reddit_primary_item(item: CollectedItem) -> bool:
    return _is_reddit_url(item.canonical_url)


def _item_marker(item: CollectedItem) -> str:
    has_rss = "rss" in item.raw_metadata
    has_reddit = "reddit" in item.raw_metadata
    if _is_reddit_primary_item(item):
        return "🔴"
    if has_rss and has_reddit:
        return "🟢"
    if has_reddit:
        return "🟠"
    return "⚪"


def _title_text(item: CollectedItem) -> str:
    prefix = "[Reddit] " if _is_reddit_primary_item(item) else ""
    return html.escape(truncate_text(f"{prefix}{item.title}", 100))


def _source_text(item: CollectedItem) -> str:
    if _is_reddit_primary_item(item):
        return html.escape(f"Source: Reddit {item.source_name.replace('r/', '/r/')}")
    return html.escape(f"Source: {item.source_name}")


def _summary_text(item: CollectedItem) -> str:
    return html.escape(truncate_text(item.summary, 135))


def _reddit_stats_text(item: CollectedItem) -> str:
    reddit = item.raw_metadata.get("reddit")
    if not reddit or not _is_reddit_primary_item(item):
        return ""
    return f"Reddit: {reddit.get('score', 0)} up | {reddit.get('num_comments', 0)} comments"


def _reddit_thread_text(item: CollectedItem) -> str:
    reddit = item.raw_metadata.get("reddit")
    if not reddit or _is_reddit_primary_item(item) or not item.discussion_url:
        return ""
    return f"Reddit thread: <a href=\"{html.escape(item.discussion_url)}\">open discussion</a>"


def _editorial_text(item: CollectedItem) -> str:
    return "Type: editorial" if "rss" in item.raw_metadata else ""


def _item_block(item: CollectedItem, index: int) -> str:
    lines = [
        f"{index}. {_item_marker(item)} <a href=\"{html.escape(item.canonical_url)}\">{_title_text(item)}</a>"
    ]
    summary = _summary_text(item)
    if summary:
        lines.append(f"<i>({summary})</i>")
    lines.append(f"└ {_source_text(item)}")

    reddit_thread = _reddit_thread_text(item)
    if reddit_thread:
        lines.append(f"└ {reddit_thread}")

    reddit_stats = _reddit_stats_text(item)
    if reddit_stats:
        lines.append(f"└ {html.escape(reddit_stats)}")

    editorial = _editorial_text(item)
    if editorial:
        lines.append(f"└ {editorial}")

    return "\n".join(lines)


def _section_header(title: str, category: str) -> str:
    emoji = SECTION_EMOJIS.get(category, "•")
    return f"<b>{emoji} {html.escape(title.upper())}</b>"


def _section(title: str, items: list[CollectedItem], category: str) -> str:
    if not items:
        return ""
    lines = [_section_header(title, category)]
    lines.extend(_item_block(item, index) for index, item in enumerate(items, start=1))
    return "\n\n".join(lines)


def _take_unique_items(
    candidates: list[CollectedItem],
    limit: int,
    used_keys: set[str],
) -> list[CollectedItem]:
    chosen: list[CollectedItem] = []
    for item in candidates:
        key = _item_key(item)
        if key in used_keys:
            continue
        chosen.append(item)
        used_keys.add(key)
        if len(chosen) >= limit:
            break
    return chosen


def _reddit_section_candidates(items: list[CollectedItem]) -> list[CollectedItem]:
    primary = [item for item in items if _is_reddit_primary_item(item)]
    discussed = [
        item
        for item in items
        if not _is_reddit_primary_item(item) and "reddit" in item.raw_metadata and item.discussion_url
    ]
    return primary + discussed


def _build_sections(items: list[CollectedItem], ranking_config: RankingConfig) -> list[str]:
    sections: list[str] = []
    used_keys: set[str] = set()

    for category in ranking_config.section_order:
        if category == "reddit":
            candidates = _reddit_section_candidates(items)
        elif category == "rss":
            candidates = [item for item in items if "rss" in item.raw_metadata]
        else:
            candidates = [item for item in items if item.category == category]

        unique_items = _take_unique_items(
            candidates,
            ranking_config.section_limits.get(category, 4),
            used_keys,
        )
        title = ranking_config.section_titles.get(category, category.replace("_", " ").title())
        section = _section(title, unique_items, category)
        if section:
            sections.append(section)
    return sections


def format_digest_messages(
    items: list[CollectedItem],
    ranking_config: RankingConfig,
) -> list[str]:
    today = datetime.now(tz=UTC).astimezone().strftime("%d/%m/%Y")
    if not items:
        return [
            (
                f"<b>My Daily Briefing | {today}</b>\n"
                "<i>No relevant items were found today.</i>\n"
                "The pipeline still completed and saved the local audit artifacts."
            )
        ]

    header = (
        f"<b>My Daily Briefing</b>\n"
        f"<i>{today} | RSS-first briefing with optional Reddit tracking</i>"
    )
    sections = [header, *_build_sections(items, ranking_config)]
    return split_messages(sections, ranking_config.telegram_message_limit)


def build_preview(messages: list[str]) -> str:
    return "\n\n---\n\n".join(messages)
