"""Configuration loading from .env and YAML."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from app.constants import (
    DEFAULT_BACKOFF_BASE_SECONDS,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_REDDIT_WINDOW_HOURS,
    DEFAULT_TELEGRAM_MESSAGE_LIMIT,
    VALIDATION_REPORT_NAME,
)
from app.models import (
    AppConfig,
    RankingConfig,
    RSSFeedConfig,
    RedditEndpointConfig,
    SourcesConfig,
    SubredditConfig,
)
from app.utils import load_json


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_app_config(root_dir: Path | None = None) -> AppConfig:
    root = root_dir or get_project_root()
    load_dotenv(root / ".env")
    return AppConfig(
        root_dir=root,
        output_dir=root / "output",
        log_dir=root / "logs",
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        reddit_user_agent=os.getenv(
            "REDDIT_USER_AGENT",
            "games-tech-digest/1.0 (+https://local.dev; contact: ops@example.com)",
        ),
        request_timeout_seconds=float(
            os.getenv("REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT_SECONDS)
        ),
        enable_reddit=_env_bool("ENABLE_REDDIT", False),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        backoff_base_seconds=float(
            os.getenv("BACKOFF_BASE_SECONDS", DEFAULT_BACKOFF_BASE_SECONDS)
        ),
    )


def load_sources_config(root_dir: Path | None = None) -> SourcesConfig:
    root = root_dir or get_project_root()
    data = _load_yaml(root / "config" / "sources.yaml")
    rss_feeds = [
        RSSFeedConfig(
            name=item["name"],
            url=item["url"],
            category=item["category"],
            limit=int(item.get("limit", 10)),
        )
        for item in data.get("rss_feeds", [])
    ]
    reddit_cfg = data.get("reddit", {})
    subreddits: list[SubredditConfig] = []
    for category, names in reddit_cfg.get("subreddits", {}).items():
        for item in names:
            subreddits.append(
                SubredditConfig(
                    name=item["name"],
                    category=category,
                    limit=int(item.get("limit", 15)),
                )
            )
    endpoints = [
        RedditEndpointConfig(
            name=item["name"],
            path=item["path"],
            enabled=bool(item.get("enabled", True)),
            params=dict(item.get("params", {})),
        )
        for item in reddit_cfg.get("endpoints", [])
    ]
    return SourcesConfig(
        rss_feeds=rss_feeds,
        reddit_subreddits=subreddits,
        reddit_validation_subreddits=list(
            reddit_cfg.get(
                "validation_subreddits",
                ["games", "technology", "pcgaming", "programming"],
            )
        ),
        reddit_time_window_hours=int(
            reddit_cfg.get("time_window_hours", DEFAULT_REDDIT_WINDOW_HOURS)
        ),
        reddit_endpoints=endpoints,
    )


def load_ranking_config(root_dir: Path | None = None) -> RankingConfig:
    root = root_dir or get_project_root()
    data = _load_yaml(root / "config" / "ranking.yaml")
    section_limits = dict(data.get("section_limits", {}))
    return RankingConfig(
        recency_window_hours=int(data.get("recency_window_hours", 24)),
        weights=dict(data.get("weights", {})),
        category_bonus=dict(data.get("category_bonus", {})),
        section_limits=section_limits,
        telegram_message_limit=int(
            data.get("telegram_message_limit", DEFAULT_TELEGRAM_MESSAGE_LIMIT)
        ),
        section_order=list(
            data.get(
                "section_order",
                ["games", "gamedev", "ai", "finance", "tech", "reddit", "rss"],
            )
        ),
        section_titles=dict(data.get("section_titles", {})),
    )


def get_validation_report_path(root_dir: Path | None = None) -> Path:
    root = root_dir or get_project_root()
    return root / "output" / VALIDATION_REPORT_NAME


def resolve_reddit_runtime_policy(app_config: AppConfig) -> dict[str, Any]:
    report = load_json(get_validation_report_path(app_config.root_dir))
    if not app_config.enable_reddit:
        return {
            "enabled": False,
            "reason": "ENABLE_REDDIT=false; RSS remains the primary source.",
            "report_found": report is not None,
        }
    if not isinstance(report, dict):
        return {
            "enabled": False,
            "reason": "Validation report not found. Reddit stays disabled until explicit validation succeeds.",
            "report_found": False,
        }
    recommendations = report.get("recommendations", {})
    if not recommendations.get("enable_reddit_optionally", False):
        return {
            "enabled": False,
            "reason": "Validation gate did not approve optional Reddit usage.",
            "report_found": True,
        }
    return {
        "enabled": True,
        "reason": "Validation gate approved optional Reddit usage.",
        "report_found": True,
        "validation_summary": report.get("summary"),
    }
