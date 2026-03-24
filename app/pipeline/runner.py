"""End-to-end digest execution."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.config import resolve_reddit_runtime_policy
from app.delivery.telegram_sender import send_telegram_messages
from app.health import HealthTracker
from app.models import AppConfig, CollectedItem, RankingConfig, SourcesConfig, TelegramSendResult
from app.pipeline.dedupe import deduplicate_items
from app.pipeline.formatter import build_preview, format_digest_messages
from app.pipeline.normalize import normalize_all
from app.pipeline.ranker import rank_items
from app.sources.reddit_json_fetcher import fetch_reddit_items
from app.sources.rss_fetcher import fetch_rss_items
from app.utils import save_json


def _serialize_runtime(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize_runtime(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_runtime(item) for key, item in value.items()}
    return value


def _save_outputs(
    *,
    output_dir: Path,
    history_dir: Path | None,
    raw_rss_items: list[dict[str, Any]],
    raw_reddit_items: list[dict[str, Any]],
    normalized_items: list[CollectedItem],
    ranked_items: list[CollectedItem],
    preview: str,
    report: dict[str, Any] | None = None,
) -> None:
    save_json(output_dir / "raw_rss_items.json", raw_rss_items)
    save_json(output_dir / "raw_reddit_items.json", raw_reddit_items)
    save_json(output_dir / "normalized_items.json", normalized_items)
    save_json(output_dir / "ranked_items.json", ranked_items)
    (output_dir / "telegram_preview.txt").write_text(preview, encoding="utf-8")
    if report is not None:
        save_json(output_dir / "last_run_report.json", report)

    if history_dir is None:
        return

    save_json(history_dir / "raw_rss_items.json", raw_rss_items)
    save_json(history_dir / "raw_reddit_items.json", raw_reddit_items)
    save_json(history_dir / "normalized_items.json", normalized_items)
    save_json(history_dir / "ranked_items.json", ranked_items)
    (history_dir / "telegram_preview.txt").write_text(preview, encoding="utf-8")
    if report is not None:
        save_json(history_dir / "run_report.json", report)


def _build_history_dir(output_dir: Path, reference: datetime, save_history: bool) -> Path | None:
    if not save_history:
        return None
    local_reference = reference.astimezone()
    date_part = local_reference.strftime("%Y-%m-%d")
    time_part = local_reference.strftime("%H-%M-%S")
    return output_dir / "history" / date_part / time_part


def run_digest(
    *,
    app_config: AppConfig,
    sources_config: SourcesConfig,
    ranking_config: RankingConfig,
    logger: logging.Logger,
    dry_run: bool = False,
    save_history: bool = True,
    rss_fetcher: Callable[..., tuple[list[dict[str, Any]], list[Any]]] = fetch_rss_items,
    reddit_fetcher: Callable[..., tuple[list[dict[str, Any]], list[Any]]] = fetch_reddit_items,
    telegram_sender: Callable[..., Any] = send_telegram_messages,
) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = datetime.now(tz=UTC)
    history_dir = _build_history_dir(app_config.output_dir, started_at, save_history)
    logger.info("Digest execution started")

    health_tracker = HealthTracker()
    reddit_policy = resolve_reddit_runtime_policy(app_config)
    if not reddit_policy["enabled"]:
        health_tracker.mark_disabled("reddit", reddit_policy["reason"])
        logger.info("Reddit disabled for this run: %s", reddit_policy["reason"])

    raw_rss_items, rss_outcomes = rss_fetcher(
        app_config=app_config,
        feeds=sources_config.rss_feeds,
        logger=logger,
    )
    raw_reddit_items: list[dict[str, Any]] = []
    reddit_outcomes: list[Any] = []
    if reddit_policy["enabled"]:
        raw_reddit_items, reddit_outcomes = reddit_fetcher(
            app_config=app_config,
            subreddits=sources_config.reddit_subreddits,
            endpoints=sources_config.reddit_endpoints,
            time_window_hours=sources_config.reddit_time_window_hours,
            request_delay_seconds=sources_config.reddit_request_delay_seconds,
            max_items_per_category=sources_config.reddit_max_items_per_category,
            max_requests_per_run=sources_config.reddit_max_requests_per_run,
            logger=logger,
            health_tracker=health_tracker,
        )

    normalized_items = normalize_all(raw_rss_items, raw_reddit_items)
    deduped_items, dedupe_stats = deduplicate_items(normalized_items)
    ranked_items = rank_items(deduped_items, ranking_config)
    messages = format_digest_messages(ranked_items, ranking_config)
    preview = build_preview(messages)
    if dry_run:
        telegram_result = TelegramSendResult(
            sent=False,
            delivered_messages=0,
            detail="Dry-run enabled. Telegram send skipped.",
        )
        logger.info("Dry-run enabled: Telegram send skipped")
    else:
        telegram_result = telegram_sender(
            app_config=app_config,
            messages=messages,
            logger=logger,
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    report = {
        "started_at": started_at.isoformat(),
        "elapsed_ms": elapsed_ms,
        "rss_items": len(raw_rss_items),
        "reddit_items": len(raw_reddit_items),
        "normalized_items": len(normalized_items),
        "deduped_items": len(deduped_items),
        "messages_generated": len(messages),
        "dry_run": dry_run,
        "reddit_policy": reddit_policy,
        "rss_outcomes": _serialize_runtime(rss_outcomes),
        "reddit_outcomes": _serialize_runtime(reddit_outcomes),
        "health": health_tracker.as_dict(),
        "dedupe_stats": dedupe_stats,
        "telegram": _serialize_runtime(telegram_result),
        "history_dir": str(history_dir) if history_dir else None,
    }
    _save_outputs(
        output_dir=app_config.output_dir,
        history_dir=history_dir,
        raw_rss_items=raw_rss_items,
        raw_reddit_items=raw_reddit_items,
        normalized_items=normalized_items,
        ranked_items=ranked_items,
        preview=preview,
        report=report,
    )
    logger.info(
        "Digest execution finished in %.2fms | RSS=%s | Reddit=%s | Ranked=%s",
        elapsed_ms,
        len(raw_rss_items),
        len(raw_reddit_items),
        len(ranked_items),
    )
    return report
