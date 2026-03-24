"""Run the full daily digest pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_app_config, load_ranking_config, load_sources_config
from app.logger import configure_logging, get_logger
from app.pipeline.runner import run_digest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the daily digest pipeline.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate outputs and preview without sending to Telegram.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip saving a dated history copy for this run.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    app_config = load_app_config(PROJECT_ROOT)
    configure_logging(app_config.log_dir, app_config.log_level)
    logger = get_logger("scripts.run_digest")

    report = run_digest(
        app_config=app_config,
        sources_config=load_sources_config(PROJECT_ROOT),
        ranking_config=load_ranking_config(PROJECT_ROOT),
        logger=logger,
        dry_run=args.dry_run,
        save_history=not args.no_history,
    )

    summary = {
        "rss_items": report["rss_items"],
        "reddit_items": report["reddit_items"],
        "messages_generated": report["messages_generated"],
        "dry_run": report["dry_run"],
        "reddit_enabled": report["reddit_policy"]["enabled"],
        "reddit_reason": report["reddit_policy"]["reason"],
        "history_dir": report["history_dir"],
        "telegram": report["telegram"]["detail"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
