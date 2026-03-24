"""Telegram-friendly formatting with dynamic sections and no repeated highlights."""

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
        return "🟥"
    if has_rss and has_reddit:
        return "🟢"
    if has_reddit:
        return "🔴"
    return "⚪"


def _source_label(item: CollectedItem) -> str:
    if _is_reddit_primary_item(item):
        return html.escape(f"Link Reddit | {item.source_name.replace('r/', '/r/')}")
    return html.escape(item.source_name.replace("r/", "Reddit /r/"))


def _meta_label(item: CollectedItem) -> str:
    labels: list[str] = []
    reddit = item.raw_metadata.get("reddit")
    if reddit and _is_reddit_primary_item(item):
        labels.append(f"{reddit.get('score', 0)} up")
        labels.append(f"{reddit.get('num_comments', 0)} comments")
    if "rss" in item.raw_metadata:
        labels.append("editorial")
    if reddit and not _is_reddit_primary_item(item):
        labels.append("discutido no Reddit")
    return " | ".join(labels)


def _item_block(item: CollectedItem, index: int) -> str:
    title_prefix = "[Reddit] " if _is_reddit_primary_item(item) else ""
    title = html.escape(truncate_text(f"{title_prefix}{item.title}", 100))
    summary = html.escape(truncate_text(item.summary, 135))
    line_1 = f"{index}. {_item_marker(item)} <a href=\"{html.escape(item.canonical_url)}\">{title}</a>"
    details = []
    if summary:
        details.append(f"<i>{summary}</i>")
    details.append(f"└ {_source_label(item)}")
    meta = _meta_label(item)
    if meta:
        details[-1] = f"{details[-1]} | {html.escape(meta)}"
    return "\n".join([line_1, *details])


def _section(title: str, items: list[CollectedItem], category: str) -> str:
    if not items:
        return ""
    emoji = SECTION_EMOJIS.get(category, "•")
    lines = [f"<b>{emoji} {html.escape(title)}</b>"]
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


def _build_sections(items: list[CollectedItem], ranking_config: RankingConfig) -> list[str]:
    sections: list[str] = []
    used_keys: set[str] = set()

    for category in ranking_config.section_order:
        if category == "reddit":
            candidates = [
                item
                for item in items
                if item.source_type == "reddit" or "reddit" in item.raw_metadata
            ]
        elif category == "rss":
            candidates = [item for item in items if "rss" in item.raw_metadata]
        else:
            candidates = [item for item in items if item.category == category]

        unique_items = _take_unique_items(
            candidates,
            ranking_config.section_limits.get(category, 3),
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
                "<i>Nenhum item relevante foi encontrado nas fontes configuradas hoje.</i>\n"
                "O pipeline rodou normalmente e manteve os arquivos de auditoria."
            )
        ]

    header = (
        f"<b>My Daily Briefing | {today}</b>\n"
        "<i>Curadoria diaria por categoria. RSS e a base; Reddit entra apenas como enriquecimento opcional.</i>"
    )
    sections = [header, *_build_sections(items, ranking_config)]
    return split_messages(sections, ranking_config.telegram_message_limit)


def build_preview(messages: list[str]) -> str:
    return "\n\n---\n\n".join(messages)
